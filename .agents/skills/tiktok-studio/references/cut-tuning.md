# Cut tuning — transcription, silences, whispers, spoken edit-cues, gaze

The cut is the highest-leverage step **and the one that fails most** — every round of feedback
on this channel has been about **silences/pauses that survived** or **garbled words**. Both
have specific, fixable causes. Be paranoid here.

## 0. Transcribe with ElevenLabs Scribe — the ONLY transcriber (whisper is banned here)

Whisper mangles every proper noun and that poisons both the captions and your own reasoning
about the cut: Claude→"Cloth", Anthropic→"Antropi", DeepSeek→"Dipsick", Qwen→"Juan/QuEED",
Kimi→"Kimmy", Ascend→"Ascent", guardrails→"Gargills". **ElevenLabs Scribe is the only
transcription method** in this project (`scripts/transcribe_elevenlabs.py`, requires
`ELEVENLABS_API_KEY`); `new.sh` errors out rather than fall back to whisper. Scribe also tags
every long pause as an `audio_event` (`"(pausa de N segundos)"`) — a free map of exactly where
the silences are. `build_cut.py` filters to `type=="word"`, so events don't reach the cut, but
READ them to spot pauses and retakes.

## 0b. Listen for SPOKEN edit instructions (this speaker narrates his retakes)

Read the FULL transcript text before cutting. This creator dictates his own edits out loud:
"Esto último está incorrecto, **Claude, elimínalo**. Este que voy a decir ahora es el correcto.",
"Eso está mal, **Claude, también elimínalo. El bueno es este.**" Each marks a flubbed take.
**Cut the flub AND the instruction phrase** (the instruction is not content). Grep the text for
`elimínalo|está mal|el bueno es este|incorrecto|otra vez|déjame` and resolve every one.

## EDL knobs (`edit/build_cut.py`, all overridable in the video's `config.py`)

| Knob | Shared default | Tight default (use this) | Purpose |
|------|------|------|---------|
| `SEGS` | — | — | `(first_word_start, last_word_start)` per kept block. Drop retakes + spoken instructions. |
| `PRE_PAD` / `POST_PAD` | 0.10 / 0.15 | **0.04 / 0.06** | breathing room before/after each take |
| `MAX_GAP` | 0.50 | **0.40** | in-take pauses longer than this are split out (a SEGMENT BOUNDARY) |
| `MAX_WORD_TAIL` | 0.90 | **0.60** | cap each word's effective end — trims trailing murmur/whisper |
| `OUT_OVERRIDES` | `{}` | — | `{last_word_start: hard_src_out}` for stubborn tails |
| `CUT_KILL` | `[]` | — | cut-timeline `(start,end)` ranges to excise post-assembly |

With accurate ElevenLabs word-ends, **set in `config.py`**: `MAX_GAP=0.40`, `PRE_PAD=0.04`,
`POST_PAD=0.06`, `MAX_WORD_TAIL=0.60`.

**Why 0.40 and NOT lower (the two-sided trap):** every gap > `MAX_GAP` becomes a *segment
boundary*, i.e. a visible **jump cut**. Setting it too low (0.22, 0.30) cut *inside* phrases —
it split "Fable" from "5", a jump cut mid-brand-name that the user flagged as "kind of cut".
But too high leaves long dead-air silences (the original complaint). The split that works:
**inter-phrase pauses are ≥~0.45s (cut them); intra-phrase rhythm is 0.2–0.4s (KEEP it)** —
`MAX_GAP=0.40` sits in that valley. The huge inter-sentence pauses are already gone because each
SEGS block is one sentence/idea, so 0.40 only governs micro-rhythm. Word inclusion uses
**start** time and clamps inflated ends to the segment out-point.

## The silence audit is MANDATORY — do not skip it

`build_cut.py` prints a **silence audit** every run: `silence audit: max inter-word gap X.XXs,
N gap(s) > <MAX_GAP+0.05>s`. The threshold scales with `MAX_GAP`, so it flags only *dead air
that survived* (a SEGS block spanning a real pause) — not the intentional intra-phrase rhythm.
It MUST be **0**. If it flags any, it lists them with cut-timeline timestamps — split the
offending SEGS block at the pause. **Never present or render a cut whose audit is non-zero.**
This catches the "too many silences" failure; the `MAX_GAP` valley (above) catches the opposite
"choppy / kind of cut" failure. Check BOTH every time.

## Whisper hunt (energy analysis)

The user gives a timestamp like "0:09". Find the exact dead/whisper window by RMS on the
**voice-only** cut (not the rendered video — music masks it):

```bash
ffmpeg -v error -ss 8.4 -t 2.0 -i IMG_<name>_cut.mp4 \
  -af astats=metadata=1:reset=1:length=0.1,ametadata=print:key=lavfi.astats.Overall.RMS_level \
  -f null - 2>&1
```

Speech sits around −10 to −25 dB; whisper/dead air drops to −35 dB and below. Cut the
low-energy span between the last audible word and the next word. Add it as a `CUT_KILL`
in **cut-timeline** seconds (stable as long as it precedes any removed segment).

`CUT_KILL` is applied by `apply_kills(edl, kills)`: it maps each cut-time range back to source
per interval and splits/trims, dropping any word that lands in the gap.

## Gaze audit (looking at camera)

A clip where the speaker looks away is not acceptable even if the audio is clean. Sample face
crops across each kept segment and inspect:

```python
# every ~0.35s, tight face crop, into a contact sheet
ffmpeg -ss T -i IMG_<name>.MOV -frames:v 1 -vf crop=1000:1000:580:850,scale=170:170 -y face.png
```

Build a labeled grid (PIL) and scan for eyes-off-camera / head-turned frames. Remove the
offending segment from `SEGS` or carve it out with a `CUT_KILL`. The two we caught in this
project were turn-away tails on "…amenaza teórica" and "…hacia China".

## Run

```bash
python3 edit/build_cut.py          # dry run — prints segments, total, mentions, long-tail flags
python3 edit/build_cut.py --cut    # encode IMG_<name>_cut.mp4
```

Joints get 12ms in/out audio fades. Always re-derive `cut_words.json` / `mentions.json` from
the same run so caption/sticker timings stay in sync.
