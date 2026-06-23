#!/usr/bin/env python3
"""Assemble videos/<name>/index.html — cut video+audio, sticker pops+SFX, captions, music,
title. Asset paths are written ROOT-relative (render runs from the repo root via `-c`).

Usage: python3 edit/build_comp.py <name>
"""
import importlib.util, json, os, re, sys

if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
    raise SystemExit("usage: build_comp.py <name>")
NAME = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "videos", NAME)
words = json.load(open(os.path.join(BASE, "cut_words.json")))
mentions = json.load(open(os.path.join(BASE, "mentions.json")))
TOTAL = json.load(open(os.path.join(BASE, "edl.json")))["total"]

# per-video config (title + accent); sensible defaults if absent
spec = importlib.util.spec_from_file_location("cfg", os.path.join(BASE, "config.py"))
cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg)
TITLE = getattr(cfg, "TITLE", "TÍTULO DEL VIDEO")
ACCENT = getattr(cfg, "ACCENT", "#487d00")
# Music: root-relative path (default = the shared track). Set MUSIC = "" / None for no music.
MUSIC = getattr(cfg, "MUSIC", "music/background-music.mp3")
MUSIC_DB = getattr(cfg, "MUSIC_DB", -15)
MUSIC_VOL = round(10 ** (MUSIC_DB / 20), 3)
# Follow/CTA scene — your channel branding (set per video in config.py).
FOLLOW_HANDLE = getattr(cfg, "FOLLOW_HANDLE", "@tuusuario")
FOLLOW_AVATAR = getattr(cfg, "FOLLOW_AVATAR", "assets/stickers/gustavo-avatar.png")
# Opt-in per video: place the avatar circle on the RIGHT side of the frame (handle + SÍGUEME
# button stay centered) instead of stacked-centered above them.
FOLLOW_AVATAR_RIGHT = getattr(cfg, "FOLLOW_AVATAR_RIGHT", False)

# Caption text corrections: whisper mishears brand names (Cloth->Claude, Dipsick->DeepSeek,
# Antropi->Anthropic, Ysi->Y si). Map is {lowercased-alpha-core: replacement}; punctuation kept.
CAPTION_FIXES = {k.lower(): v for k, v in getattr(cfg, "CAPTION_FIXES", {}).items()}
def fix_word(t):
    m = re.match(r"^([^\wáéíóúñ]*)(.*?)([^\wáéíóúñ]*)$", t, re.I)
    pre, core, post = m.groups()
    rep = CAPTION_FIXES.get(core.lower())
    return f"{pre}{rep}{post}" if rep else t

# Title band bottom = where the hair starts (measured per video by detect_head_bounds.py).
try:
    HAIRLINE = int(open(os.path.join(BASE, "hairline.txt")).read().strip())
except Exception:
    HAIRLINE = 500
# Sticker top FLOOR = a safe Y below the chin (measured per video by detect_head_bounds.py). Every
# overlay's top edge stays below this so images never touch/block the head. Fallback = legacy 1120.
try:
    CHIN = int(open(os.path.join(BASE, "chin.txt")).read().strip())
except Exception:
    CHIN = 1120

# ---- sticker events: pop on mention, truncate before the next mention ----
stickers = []
for i, m in enumerate(mentions):
    start = max(m["time"] - 0.12, 0)
    dur = 2.8
    if i + 1 < len(mentions):
        dur = min(dur, max(mentions[i + 1]["time"] - 0.12 - start - 0.06, 0.6))
    stickers.append({"brand": m["brand"], "start": round(start, 3), "dur": round(dur, 3)})

# ---- follow/CTA scene: house format ALWAYS ends on it. Auto-append a "follow" card over the
# last few seconds unless config already placed one via a (src, "follow") mention. (Without this
# the avatar + @handle + SÍGUEME button never render — there is no other code that adds it.) ----
FOLLOW_DUR = 3.5
if not any(s["brand"] == "follow" for s in stickers):
    f_start = max(TOTAL - FOLLOW_DUR,
                  (stickers[-1]["start"] + stickers[-1]["dur"] + 0.1) if stickers else 0.0)
    stickers.append({"brand": "follow", "start": round(f_start, 3),
                     "dur": round(max(TOTAL - f_start, 0.6), 3)})

# ---- sticker spread audit (Hard Rule 9): at most STICKER_MAX, >= STICKER_MIN_GAP apart ----
# The min-gap is WAIVED for enumerations — back-to-back stickers tighter than STICKER_ENUM_GAP
# are treated as an intentional list (naming several companies/people/examples in a row).
# Warnings are printed at the end so they can be relayed to the user, like the silence audit.
STICKER_MAX = getattr(cfg, "STICKER_MAX", 15)
STICKER_MIN_GAP = getattr(cfg, "STICKER_MIN_GAP", 5.0)
STICKER_ENUM_GAP = getattr(cfg, "STICKER_ENUM_GAP", 2.0)
content_stk = [s for s in stickers if s["brand"] != "follow"]  # the CTA/follow card is exempt
sticker_warnings = []
if len(content_stk) > STICKER_MAX:
    sticker_warnings.append(
        f"{len(content_stk)} stickers exceed the max of {STICKER_MAX} — drop the "
        f"{len(content_stk) - STICKER_MAX} weakest (keep them spread across the video).")
for a, b in zip(content_stk, content_stk[1:]):
    gap = b["start"] - a["start"]
    if STICKER_ENUM_GAP <= gap < STICKER_MIN_GAP:
        sticker_warnings.append(
            f"gap {gap:.1f}s between '{a['brand']}' (t={a['start']:.1f}s) and '{b['brand']}' "
            f"(t={b['start']:.1f}s) is <{STICKER_MIN_GAP:.0f}s and not a tight enumeration "
            f"(<{STICKER_ENUM_GAP:.0f}s) — spread them out, or confirm it's an intentional list.")

# sticker on-screen windows (with small guard) — captions must not coexist with these
GUARD = 0.05
sticker_ivals = [(s["start"] - GUARD, s["start"] + s["dur"] + GUARD) for s in stickers]

def free_window(gs, ge):
    """Largest caption window inside [gs,ge] not covered by any sticker; None if too short."""
    s, e = gs, ge
    for vs, ve in sticker_ivals:
        if ve <= s or vs >= e:
            continue
        if vs <= s and ve >= e:
            return None                  # fully covered by a sticker
        if vs <= s < ve:
            s = ve                       # sticker covers the head → start after it
        elif vs < e <= ve:
            e = vs                       # sticker covers the tail → end before it
        elif vs > s and ve < e:
            e = vs                       # sticker strictly inside → show head, end at pop
    return (s, e) if e - s >= 0.4 else None

# ---- caption groups: max 4 words, break on pauses and punctuation ----
groups, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    hard = re.search(r"[.!?:…]$", w["text"]) is not None
    comma = w["text"].endswith(",") and len(cur) >= 3
    gap = nxt and (nxt["start"] - w["end"]) > 0.35
    if hard or comma or gap or len(cur) >= 4 or not nxt:
        groups.append(cur)
        cur = []

cap_groups = []
for gi, g in enumerate(groups):
    raw_show = g[0]["start"] - 0.08
    raw_end = (min(g[-1]["end"] + 0.7, groups[gi + 1][0]["start"] - 0.05)
               if gi + 1 < len(groups) else min(g[-1]["end"] + 0.8, TOTAL - 0.1))
    raw_end = max(raw_end, g[-1]["end"] + 0.05)
    win = free_window(max(raw_show, 0.12), raw_end)
    if win is None:
        continue                         # hidden — a sticker owns this moment
    show, end = win
    cap_groups.append({
        "start": round(show, 3), "end": round(end, 3),
        "words": [{"t": fix_word(w["text"]), "s": round(w["start"], 3), "e": round(w["end"], 3)} for w in g],
    })

from PIL import Image
FRAME_BOTTOM_PAD = 40  # keep stickers off the very bottom edge
def stk_geom(brand):
    w, h = Image.open(os.path.join(BASE, f"stickers/{brand}.png")).size
    ar = w / h
    width = max(320, min(720, int((202500 * ar) ** 0.5)))  # ~450x450 visual area
    height = int(width / ar)
    # The sticker TOP must stay below CHIN (the per-video chin floor) so it never touches the
    # head. If a tall sticker wouldn't fit between CHIN and the frame bottom, shrink it (keep AR).
    avail = (1920 - FRAME_BOTTOM_PAD) - CHIN
    if height > avail:
        height = avail
        width = int(height * ar)
    top = max(CHIN, 1400 - height // 2)  # below the chin; otherwise centered at chest (y~1400)
    if top + height > 1920 - FRAME_BOTTOM_PAD:
        top = 1920 - FRAME_BOTTOM_PAD - height
    return width, height, top

FOLLOW_HTML = (
    '      <div class="clip stk follow-scene{favcls}" id="stk-{i}" '
    'style="width:560px;margin-left:-280px;top:{chin}px" '
    'data-start="{start}" data-duration="{dur}" data-track-index="2">\n'
    '        <img class="fav" src="{avatar}" alt="" />\n'
    '        <div class="fhandle">{handle}</div>\n'
    '        <div class="fbtn"><span class="fplus">+</span>SÍGUEME</div>\n'
    '      </div>')

def sticker_html(i, s):
    if s["brand"] == "follow":
        return FOLLOW_HTML.format(i=i, start=s["start"], dur=s["dur"], chin=CHIN,
                                  avatar=FOLLOW_AVATAR, handle=FOLLOW_HANDLE,
                                  favcls=" fav-right" if FOLLOW_AVATAR_RIGHT else "")
    w, h, top = stk_geom(s["brand"])
    # explicit width AND height (+ object-fit in CSS) so the renderer can't stretch via height:auto
    return (f'      <img class="clip stk" id="stk-{i}" src="videos/{NAME}/stickers/{s["brand"]}.png" '
            f'style="width:{w}px;height:{h}px;margin-left:-{w//2}px;top:{top}px" '
            f'data-start="{s["start"]}" data-duration="{s["dur"]}" data-track-index="2" alt="" />')

sticker_imgs = "\n".join(sticker_html(i, s) for i, s in enumerate(stickers))

sfx_audio = "\n".join(
    f'      <audio class="clip" id="sfx-{i}" src="assets/sfx/pop-click.mp3" '
    f'data-start="{s["start"]}" data-duration="0.55" data-track-index="5" data-volume="0.6"></audio>'
    for i, s in enumerate(stickers))

HTML = """<!DOCTYPE html>
<html lang="es" data-composition-variables='[{"id":"title","type":"string","label":"Título","default":"__TITLE__"},{"id":"accent","type":"color","label":"Color de resaltado","default":"__ACCENT__"}]'>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #000; }
      #main {
        position: relative; width: 1080px; height: 1920px;
        font-family: "Outfit", sans-serif; overflow: hidden;
      }
      #intro-wrap { position: absolute; inset: 0; transform-origin: 50% 50%; }
      #base-video { position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }
      .stk {
        position: absolute; left: 50%; object-fit: contain;
        /* grow from the BOTTOM so the back.out pop overshoot never extends the top edge upward
           into the chin/head — the top only ever reaches its resting (below-chin) position. */
        z-index: 5; transform: scale(0); transform-origin: 50% 100%;
        filter: drop-shadow(0 14px 30px rgba(0, 0, 0, 0.45));
      }
      /* follow scene: avatar + handle + button stacked, centered */
      .follow-scene { display: flex; flex-direction: column; align-items: center; gap: 22px; }
      .follow-scene .fav { width: 230px; height: 230px; }
      /* avatar pulled out to the RIGHT side of the frame (handle + button stay centered) */
      .follow-scene.fav-right { min-height: 300px; justify-content: center; }
      .follow-scene.fav-right .fav { position: absolute; left: 540px; top: 0; }
      .follow-scene .fhandle {
        font-weight: 800; font-size: 50px; color: #fff; letter-spacing: 0.5px;
        background: rgba(8,8,10,0.9); padding: 10px 26px; border-radius: 16px;
      }
      .follow-scene .fbtn {
        display: inline-flex; align-items: center; gap: 18px;
        background: #ef4444; color: #fff; font-weight: 800; font-size: 58px;
        text-transform: uppercase; letter-spacing: 1px;
        padding: 22px 52px 22px 40px; border-radius: 60px; border: 5px solid #fff;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
      }
      .follow-scene .fplus {
        display: inline-flex; align-items: center; justify-content: center;
        width: 56px; height: 56px; border-radius: 50%; background: #fff; color: #ef4444;
        font-size: 52px; line-height: 1; padding-bottom: 6px;
      }
      /* title: sits in the band between the top of frame and the hairline (measured per video →
         __HAIRLINE__px here; do NOT hardcode across videos). Biased toward the LOWER part of the
         band (padding-top below) so it nestles just above the head — a centered-in-[0,hairline]
         card reads as top-heavy because people perceive "where my hair starts" as the forehead
         hairline, not the top of the curls. */
      #title-card {
        position: absolute; top: 0; left: 0; right: 0; height: __HAIRLINE__px; z-index: 7;
        display: flex; align-items: center; justify-content: center; padding: __TITLE_PADTOP__px 70px 0;
      }
      #title-card .card {
        display: inline-block; color: #ffffff;
        font-weight: 800; text-transform: uppercase; letter-spacing: 1px;
        line-height: 1.12; padding: 22px 36px; border-radius: 0;
        max-width: 880px; font-size: 66px; text-align: center;
        white-space: pre-line;   /* honor an explicit "\n" in a two-line TITLE */
        /* liquid-glass: DARK translucent fill + backdrop blur + faint rim (kept dark, not gray) */
        background: rgba(3, 4, 7, 0.46);
        border: 1.5px solid rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(18px) saturate(125%);
        -webkit-backdrop-filter: blur(18px) saturate(125%);
        box-shadow: 0 10px 34px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.14);
        text-shadow: 0 2px 12px rgba(0, 0, 0, 0.7);
      }
      /* captions: chest zone (same place as stickers); centered at y~1400 */
      #captions {
        position: absolute; left: 0; right: 0; top: 1180px; height: 440px; z-index: 6;
        display: flex; align-items: center; justify-content: center;
      }
      .cgroup {
        position: absolute; left: 0; right: 0; top: 0; bottom: 0;
        display: flex; align-items: center; justify-content: center;
        opacity: 0; visibility: hidden;
        font-weight: 800; line-height: 1.16; text-transform: uppercase; letter-spacing: 0.5px;
      }
      /* captions: no container box; white-filled letters with a black outline. The active
         (karaoke) word gets a square accent-colored BLOCK behind it (set per-word in JS). */
      .cgroup .cbg {
        display: inline-block; max-width: 920px; text-align: center;
      }
      .cgroup .w {
        display: inline-block; transform-origin: 50% 60%; padding: 2px 10px;
        color: #ffffff; -webkit-text-stroke: 5px #000000; paint-order: stroke fill;
        background-color: transparent; border-radius: 0;   /* square block when highlighted */
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
      }
    </style>
  </head>
  <body>
    <div id="main" data-composition-id="main" data-start="0" data-duration="__TOTAL__" data-width="1080" data-height="1920">
      <div id="intro-wrap">
        <video id="base-video" class="clip" src="videos/__NAME__/cut.mp4" data-start="0" data-duration="__TOTAL__" data-track-index="0" muted playsinline></video>
      </div>
      <audio id="base-audio" class="clip" src="videos/__NAME__/cut.mp4" data-start="0" data-duration="__TOTAL__" data-track-index="1" data-volume="1"></audio>
__MUSIC_AUDIO__
      <audio id="sfx-camera" class="clip" src="assets/sfx/camera.mp3" data-start="0.05" data-duration="0.35" data-track-index="7" data-volume="0.7"></audio>
__SFX_AUDIO__
__STICKER_IMGS__
      <div id="captions" class="clip" data-start="0" data-duration="__TOTAL__" data-track-index="3"></div>
      <div id="title-card" class="clip" data-start="0" data-duration="__TOTAL__" data-track-index="4"><span class="card" id="title-text"></span></div>

      <script>
        var GROUPS = __GROUPS_JSON__;
        var STICKERS = __STICKERS_JSON__;
        var ACCENT = "__ACCENT__"; // fallback — edit ACCENT in videos/<name>/config.py
        if (window.__hyperframes && window.__hyperframes.getVariables) {
          var v0 = window.__hyperframes.getVariables();
          if (v0 && v0.accent) ACCENT = v0.accent;
        }

        // Editable title (composition variable "title"; default from config.py)
        var titleText = "__TITLE__";
        if (window.__hyperframes && window.__hyperframes.getVariables) {
          var vars = window.__hyperframes.getVariables();
          if (vars && vars.title) titleText = vars.title;
        }
        var titleEl = document.getElementById("title-text");
        titleEl.textContent = titleText;
        // auto-fit: start at 66px (0.75x), shrink until the card holds at most two lines
        var tFont = 66;
        titleEl.style.fontSize = tFont + "px";
        while (tFont > 40 && titleEl.getBoundingClientRect().height > tFont * 1.12 * 2 + 48) {
          tFont -= 3;
          titleEl.style.fontSize = tFont + "px";
        }

        // Build caption DOM synchronously (white words; active word gets an accent block)
        var capRoot = document.getElementById("captions");
        GROUPS.forEach(function (g, gi) {
          var div = document.createElement("div");
          div.className = "cgroup";
          div.id = "cg-" + gi;
          var bg = document.createElement("span");
          bg.className = "cbg";
          g.words.forEach(function (w, wi) {
            var span = document.createElement("span");
            span.className = "w";
            span.id = "w-" + gi + "-" + wi;
            span.textContent = w.t;
            bg.appendChild(span);
            if (wi < g.words.length - 1) bg.appendChild(document.createTextNode(" "));
          });
          div.appendChild(bg);
          capRoot.appendChild(div);
          var text = g.words.map(function (w) { return w.t; }).join(" ").toUpperCase();
          var size = 62;
          if (window.__hyperframes && window.__hyperframes.fitTextFontSize) {
            size = window.__hyperframes.fitTextFontSize(text, {
              fontFamily: "Outfit", fontWeight: 800,
              maxWidth: 840, baseFontSize: 62, minFontSize: 40,
            }).fontSize;
          }
          div.style.fontSize = size + "px";
        });

        window.__timelines = window.__timelines || {};
        var tl = gsap.timeline({ paused: true });

        // Intro: zoom + fade over the first ~1.3s (camera SFX fires at 0.05s)
        tl.fromTo("#intro-wrap", { scale: 1.18, opacity: 0 },
          { scale: 1, opacity: 1, duration: 1.3, ease: "power2.out" }, 0);

        // Title entrance
        tl.fromTo("#title-card .card", { y: -60, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, 0.15);

        // Sticker pops (scale only — the framework owns clip opacity)
        STICKERS.forEach(function (s, i) {
          var sel = "#stk-" + i;
          tl.fromTo(sel, { scale: 0, rotation: -10 },
            { scale: 1, rotation: 0, duration: 0.45, ease: "back.out(1.7)" }, s.start);
          var outDur = Math.min(0.22, s.dur * 0.3);
          tl.to(sel, { scale: 0, rotation: 6, duration: outDur, ease: "power3.in" },
            s.start + s.dur - outDur - 0.02);
        });

        // Captions: pop in, karaoke word highlight, hard kill
        GROUPS.forEach(function (g, gi) {
          var el = "#cg-" + gi;
          tl.set(el, { visibility: "visible" }, g.start);
          tl.fromTo(el, { opacity: 0, scale: 0.9, y: 16 },
            { opacity: 1, scale: 1, y: 0, duration: 0.18, ease: "back.out(2)" }, g.start);
          g.words.forEach(function (w, wi) {
            var ws = "#w-" + gi + "-" + wi;
            var hot = Math.max(w.s, g.start + 0.02);
            if (hot >= g.end) return;    // word falls outside the visible window
            // active: square accent-colored block appears behind the white word (transient —
            // only the current word is lit; it clears as the next word activates)
            tl.set(ws, { backgroundColor: ACCENT, scale: 1.05 }, hot);
            var revert = wi < g.words.length - 1 ? g.words[wi + 1].s : Math.min(w.e + 0.08, g.end - 0.1);
            tl.set(ws, { backgroundColor: "transparent", scale: 1 }, Math.min(Math.max(revert, hot + 0.05), g.end - 0.02));
          });
          tl.to(el, { opacity: 0, scale: 0.95, duration: 0.12, ease: "power2.in" }, g.end - 0.12);
          tl.set(el, { opacity: 0, visibility: "hidden" }, g.end);
        });

        // Caption self-lint: every group hidden after its end
        GROUPS.forEach(function (g, gi) {
          var el = document.getElementById("cg-" + gi);
          if (!el) return;
          tl.seek(g.end + 0.01);
          var cs = window.getComputedStyle(el);
          if (cs.opacity !== "0" && cs.visibility !== "hidden") {
            console.warn("[caption-lint] group " + gi + " visible at t=" + (g.end + 0.01).toFixed(2));
          }
        });
        tl.seek(0);

        window.__timelines["main"] = tl;
      </script>
    </div>
  </body>
</html>
"""

music_audio = (f'      <audio id="bg-music" class="clip" src="{MUSIC}" data-start="0" '
               f'data-duration="{TOTAL}" data-track-index="6" data-volume="{MUSIC_VOL}"></audio>'
               if MUSIC else "")

out = (HTML
       .replace("__NAME__", NAME)
       # Escape the title so a multi-line title (TITLE with "\n") stays valid in BOTH the
       # data-composition-variables JSON attribute AND the inline `var titleText="..."` JS.
       # json.dumps()[1:-1] yields \n / \" escapes (no outer quotes); CSS white-space:pre-line
       # on the card turns the runtime newline into a real second line.
       .replace("__TITLE__", json.dumps(TITLE)[1:-1])
       .replace("__ACCENT__", ACCENT)
       .replace("__TOTAL__", str(TOTAL))
       .replace("__HAIRLINE__", str(HAIRLINE))
       .replace("__TITLE_PADTOP__", str(round(0.16 * HAIRLINE)))
       .replace("__MUSIC_AUDIO__", music_audio)
       .replace("__STICKER_IMGS__", sticker_imgs)
       .replace("__GROUPS_JSON__", json.dumps(cap_groups, ensure_ascii=False))
       .replace("__SFX_AUDIO__", sfx_audio)
       .replace("__STICKERS_JSON__", json.dumps(stickers)))
open(os.path.join(BASE, "index.html"), "w").write(out)
print(f"[{NAME}] index.html: {len(cap_groups)} caption groups, {len(stickers)} stickers, "
      f"title {TITLE!r}, music {MUSIC or 'none'} ({MUSIC_DB}dB), hairline {HAIRLINE}, total {TOTAL}s")

# Sticker spread audit — relay any of these to the user before render (like the silence audit).
if sticker_warnings:
    print(f"[{NAME}] STICKER AUDIT — review before render ({len(sticker_warnings)} flag(s)):")
    for w in sticker_warnings:
        print(f"  - {w}")
else:
    print(f"[{NAME}] sticker audit: OK ({len(content_stk)} stickers, "
          f"max {STICKER_MAX}, all >= {STICKER_MIN_GAP:.0f}s apart or enumerations)")
