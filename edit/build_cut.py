#!/usr/bin/env python3
"""Build the best-takes EDL for ONE video and cut it (HLG->SDR), per-video subfolder.

Usage: python3 edit/build_cut.py <name> [--cut]
Reads:  videos/<name>/config.py  (SEGS, MENTIONS, optional OUT_OVERRIDES/CUT_KILL)
        videos/<name>/transcript.json
        videos/<name>/source.MOV
Writes: videos/<name>/{edl,cut_words,mentions}.json   (always)
        videos/<name>/cut.mp4                          (with --cut)

Dry run (no --cut) prints stats so you can tune SEGS before the slow encode.
See the tiktok-studio skill, references/cut-tuning.md.
"""
import importlib.util, json, subprocess, sys, os

if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
    raise SystemExit("usage: build_cut.py <name> [--cut]")
NAME = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "videos", NAME)
SRC = os.path.join(BASE, "source.MOV")
OUT = os.path.join(BASE, "cut.mp4")

# per-video config
spec = importlib.util.spec_from_file_location("cfg", os.path.join(BASE, "config.py"))
cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg)
SEGS = cfg.SEGS
MENTIONS = getattr(cfg, "MENTIONS", [])
OUT_OVERRIDES = getattr(cfg, "OUT_OVERRIDES", {})
CUT_KILL = getattr(cfg, "CUT_KILL", [])
# {first_word_start: extra_lead_seconds} — pull a segment's IN-point earlier into the preceding
# silence so a hard-onset word (e.g. "xAI" after a long pause) gets a clean lead-in and isn't
# eaten by the 12ms fade-in. Keyed by the word's source start.
IN_EXTEND = getattr(cfg, "IN_EXTEND", {})
if not SEGS:
    raise SystemExit(f"videos/{NAME}/config.py: SEGS is empty — fill it from the transcript "
                     "(see the tiktok-studio skill, references/cut-tuning.md).")

# Source is iPhone HDR (BT.2020 / HLG / Dolby Vision). We tone-map HLG -> SDR Rec.709 here so
# the cut is true SDR. Needs an ffmpeg WITH zscale (stock Homebrew lacks it). See
# the tiktok-studio skill's references/color-and-export.md.
FFMPEG = os.environ.get("FFMPEG_TONEMAP") or os.path.expanduser("~/.local/bin/ffmpeg-tonemap")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"
TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:p=bt709:r=tv,format=yuv420p")

d = json.load(open(os.path.join(BASE, "transcript.json")))
# Accept both transcript shapes: ElevenLabs {"words":[{...,"type"}]} and the flat Whisper /
# `hyperframes transcribe` array [{"text","start","end"}].
raw = d["words"] if isinstance(d, dict) and "words" in d else d
words = [w for w in raw if w.get("type", "word") == "word" and "start" in w]

# Defaults; a video's config.py may override any of these to tune pacing / silence removal.
PRE_PAD = getattr(cfg, "PRE_PAD", 0.10)
POST_PAD = getattr(cfg, "POST_PAD", 0.15)
MAX_GAP = getattr(cfg, "MAX_GAP", 0.50)              # internal pauses longer than this get compressed
MAX_WORD_TAIL = getattr(cfg, "MAX_WORD_TAIL", 0.90)  # cap inflated final-word ends over trailing murmur

def eff_end(w):
    return min(w["end"], w["start"] + MAX_WORD_TAIL)

def apply_kills(intervals, kills):
    """Remove cut-time `kills` ranges from source `intervals` (list of (src_in,src_out))."""
    out, off = [], 0.0
    for a, b in intervals:
        cs, ce = off, off + (b - a)
        off = ce
        pieces = [(a, b)]
        for ks, ke in kills:
            ks2, ke2 = max(ks, cs), min(ke, ce)
            if ke2 <= ks2:
                continue
            sks, ske = a + (ks2 - cs), a + (ke2 - cs)
            np = []
            for s0, s1 in pieces:
                if ske <= s0 or sks >= s1:
                    np.append((s0, s1))
                else:
                    if s0 < sks:
                        np.append((s0, sks))
                    if ske < s1:
                        np.append((ske, s1))
            pieces = np
        out.extend(pieces)
    return out

def word_at(start):
    w = min(words, key=lambda x: abs(x["start"] - start))
    if abs(w["start"] - start) > 0.30:
        raise SystemExit(f"no word near {start} (closest {w['start']} {w['text']!r})")
    return w

# padded in/out, clamped to neighbouring speech, split at internal pauses > MAX_GAP
edl = []
for first, last in SEGS:
    w_in, w_out = word_at(first), word_at(last)
    prev_end = max((w["end"] for w in words if w["end"] <= w_in["start"] - 0.01), default=0)
    next_start = min((w["start"] for w in words if w["start"] >= w_out["end"] + 0.01), default=1e9)
    t_in = max(w_in["start"] - PRE_PAD, prev_end + 0.02, 0)
    t_out = min(eff_end(w_out) + POST_PAD, next_start - 0.02)
    if w_out["start"] in OUT_OVERRIDES:
        t_out = min(t_out, OUT_OVERRIDES[w_out["start"]])
    inside = [w for w in words if w["start"] >= w_in["start"] and w["start"] <= w_out["start"]]
    sub_start = t_in
    for a, b in zip(inside, inside[1:]):
        if b["start"] - eff_end(a) > MAX_GAP:
            edl.append((sub_start, eff_end(a) + POST_PAD))
            lead = next((v for k, v in IN_EXTEND.items() if abs(k - b["start"]) < 0.05), 0)
            sub_start = max(b["start"] - PRE_PAD - lead, eff_end(a) + POST_PAD + 0.02)
    edl.append((sub_start, t_out))

edl = apply_kills(edl, CUT_KILL)

# remap words + mentions into the cut timeline
offset = 0.0
cut_words, seg_meta = [], []
for (t_in, t_out) in edl:
    for w in words:
        if w["start"] >= t_in and w["start"] < t_out - 0.04:
            cut_words.append({"text": w["text"], "start": round(w["start"] - t_in + offset, 3),
                              "end": round(min(w["end"], t_out) - t_in + offset, 3), "src_start": w["start"]})
    seg_meta.append({"src_in": round(t_in, 3), "src_out": round(t_out, 3),
                     "cut_in": round(offset, 3), "dur": round(t_out - t_in, 3)})
    offset += t_out - t_in
total = offset

mentions = []
for src, brand in MENTIONS:
    hit = next((w for w in cut_words if abs(w["src_start"] - src) < 0.30), None)
    if not hit:
        raise SystemExit(f"mention {brand}@{src} not inside any kept segment")
    mentions.append({"brand": brand, "time": hit["start"], "word": hit["text"]})

json.dump({"segments": seg_meta, "total": round(total, 3)}, open(os.path.join(BASE, "edl.json"), "w"), indent=1)
json.dump(cut_words, open(os.path.join(BASE, "cut_words.json"), "w"), ensure_ascii=False, indent=1)
json.dump(mentions, open(os.path.join(BASE, "mentions.json"), "w"), indent=1)
print(f"[{NAME}] {len(edl)} segments, {total:.2f}s ({total/60:.2f} min), "
      f"{len(cut_words)} words, {len(mentions)} mentions")

# --- SILENCE AUDIT (the #1 failure mode) — every gap between consecutive kept words. ---
# After splitting at MAX_GAP, no kept gap should exceed it by more than a hair. A gap beyond
# MAX_GAP+0.05 is genuine dead air that survived (bad SEGS spanning a pause) — fix it. NOTE: do
# NOT just lower MAX_GAP to zero — gaps below ~0.34 are natural intra-phrase rhythm; cutting
# them creates mid-phrase JUMP CUTS (e.g. a boundary between "Fable" and "5"). Keep rhythm, cut pauses.
SILENCE_WARN = round(MAX_GAP + 0.05, 2)
gaps = sorted(((cut_words[i + 1]["start"] - cut_words[i]["end"], cut_words[i]["text"],
               cut_words[i + 1]["text"], cut_words[i]["end"]) for i in range(len(cut_words) - 1)),
              reverse=True)
flagged = [g for g in gaps if g[0] > SILENCE_WARN]
mx = gaps[0][0] if gaps else 0.0
print(f"[{NAME}] silence audit: max inter-word gap {mx:.2f}s, {len(flagged)} gap(s) > {SILENCE_WARN}s")
if flagged:
    print(f"[{NAME}] ⚠ PAUSES SURVIVED — review/tighten (MAX_GAP={MAX_GAP}, MAX_WORD_TAIL={MAX_WORD_TAIL}):")
    for g, a, b, at in flagged[:8]:
        print(f"       {g:.2f}s at cut t={at:.1f}s  …{a!r} | {b!r}…")

if "--cut" not in sys.argv:
    sys.exit(0)

# ffmpeg: per-segment trim, HLG->SDR tone-map, scale 1080x1920@60, 12ms audio fades
fc, vlabels, alabels = [], [], []
for i, (t_in, t_out) in enumerate(edl):
    dur = t_out - t_in
    fc.append(f"[0:v]trim=start={t_in:.3f}:end={t_out:.3f},setpts=PTS-STARTPTS[v{i}]")
    fc.append(f"[0:a]atrim=start={t_in:.3f}:end={t_out:.3f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.012,afade=t=out:st={max(dur-0.012,0):.3f}:d=0.012[a{i}]")
    vlabels.append(f"[v{i}]"); alabels.append(f"[a{i}]")
fc.append("".join(f"{v}{a}" for v, a in zip(vlabels, alabels)) + f"concat=n={len(edl)}:v=1:a=1[vc][ac]")
fc.append(f"[vc]{TONEMAP},scale=1080:1920:flags=lanczos,fps=60[vout]")
if "zscale" not in subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True).stdout:
    raise SystemExit(f"{FFMPEG} lacks zscale — install a tone-map ffmpeg to ~/.local/bin/ffmpeg-tonemap "
                     "(see the tiktok-studio skill, references/color-and-export.md).")
cmd = [FFMPEG, "-y", "-i", SRC, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[ac]",
       "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
       "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
       "-c:a", "aac", "-b:a", "192k", OUT]
print(f"[{NAME}] cutting (HLG->SDR tone-map) -> {OUT} ...")
subprocess.run(cmd, check=True, capture_output=True)
print("wrote", OUT)

# --- RMS SILENCE AUDIT (catches dead air the word-gap audit can't see) -----------------------
# The word-gap audit trusts transcript timestamps, but Scribe often tags a word's START well
# before its real onset after a pause (a held "Eeees" / "¿Túuu"), hiding ~1s of silence INSIDE
# the word's span. Decode the rendered cut's audio and flag any near-silent run > 0.5s — those
# are real "stops" to remove with CUT_KILL (in CUT-timeline seconds).
import struct, math
raw_audio = subprocess.run([FFMPEG, "-v", "error", "-i", OUT, "-ac", "1", "-ar", "8000",
                            "-f", "f32le", "-"], capture_output=True).stdout
s = struct.unpack("<%df" % (len(raw_audio) // 4), raw_audio)
sr, win = 8000, int(8000 * 0.05)
env = [math.sqrt(sum(v * v for v in s[i:i + win]) / win) for i in range(0, len(s) - win, win)]
TH, MINLEN = 0.02, int(0.5 / 0.05)
runs, i = [], 0
while i < len(env):
    if env[i] < TH:
        j = i
        while j < len(env) and env[j] < TH:
            j += 1
        if j - i >= MINLEN:
            runs.append((i * 0.05, j * 0.05, (j - i) * 0.05))
        i = j
    else:
        i += 1
print(f"[{NAME}] RMS silence audit: {len(runs)} dead-air run(s) > 0.5s in the cut")
if runs:
    print(f"[{NAME}] ⚠ DEAD AIR — trim with CUT_KILL = [(start,end), ...] (cut-timeline seconds):")
    for a, b, d in runs:
        print(f"       {a:6.2f} - {b:6.2f}  ({d:.2f}s)")
