---
name: tiktok-studio
description: >-
  Turn a vertical talking-head recording (raw .MOV/.mp4 with retakes + a word-level
  transcript) into a finished TikTok edit: cut to the best takes with whispers/gaze-aways
  removed, AI cartoon "sticker" overlays synced to spoken brands/actions, karaoke captions,
  a persistent editable glass title card, intro zoom + SFX, and a ducked music bed. Built
  on HyperFrames (HTML compositions). Use whenever the user wants to edit one of their
  talking-head/TikTok videos in this studio format, add synced cartoon images, restyle the
  captions/title, swap sound effects, or re-cut to tighten pauses. ALWAYS suggest 5 short
  catchy titles before finalizing.
---

# TikTok Studio Edit

A repeatable pipeline for the user's vertical talking-head TikToks. The face and 9:16 ratio
are **never** altered — everything is overlay, timing, and audio on top of the original frame.

> Read the `hyperframes`, `hyperframes-cli`, and `hyperframes-media` skills for framework
> mechanics. This skill is the **house format** layered on top of them.

## HARD RULES (do these every time)

1. **Always suggest 5 short, catchy titles** (≤ ~6 words each) in the **video's spoken
   language** (detect from the transcript — Spanish for the current project). Present them
   and let the user pick or tweak before the final render. The title is an editable
   composition variable, so changing it later costs nothing.
2. **Never crop, zoom, or reframe the person.** Keep the original 1080×1920 frame and the
   face exactly as shot. Overlays go in the margins (title above the head, images/captions at
   chest height).
3. **Cut quality first — this is where you fail most, so be paranoid.** (a) **Transcribe with
   ElevenLabs Scribe, never whisper-small** — whisper mangles proper nouns (Claude→"Cloth",
   DeepSeek→"Dipsick", Qwen→"Juan"). `new.sh` defaults to Scribe. (b) **Read the full transcript
   and cut every spoken edit instruction** — this creator dictates retakes out loud ("Claude,
   elimínalo", "eso está mal, el bueno es este"); cut the flub AND the instruction. (c) **No
   silence is acceptable, but no JUMP CUTS either** — `MAX_GAP=0.40` (NOT lower: 0.22/0.30 cut
   mid-phrase, e.g. between "Fable" and "5"), `PRE_PAD=0.04`, `POST_PAD=0.06`,
   `MAX_WORD_TAIL=0.60` in `config.py`. Then **obey the silence audit** `build_cut.py` prints —
   it MUST be **0** flagged gaps before you preview or render. Build `SEGS`/`MENTIONS` from THIS
   video's transcript every time. See "Cut" for the pause-vs-jump-cut valley.
   (d) **The final edit MUST be under 3:00** (≤ ~180s). If the clean takes run longer, cut content
   (drop the weakest digressions) — never ship ≥ 3 min. Confirm via `build_cut.py`'s reported total.
4. **Captions and chest-height images are mutually exclusive in time.** When an image pops,
   the caption for that moment is suppressed; captions only fill the gaps. Verify zero
   overlap before rendering.
5. **Determinism + clips.** No `Math.random`/`Date.now`. Every overlay (captions container,
   title, stickers, SFX, music) MUST be a `class="clip"` element on a track **above** the
   video — non-clip elements render *under* the video and vanish. (See
   [references/hyperframes-gotchas.md](references/hyperframes-gotchas.md).)
6. After any change: `npm run check` (lint + validate + inspect) must pass, then render and
   **QC actual frames** (extract with ffmpeg and look at them).
7. **Deliver SDR Rec.709, never raw HDR.** The iPhone source is HDR (BT.2020/HLG/Dolby
   Vision); uploading HDR makes IG/FB look dark and TikTok look gray. Always tone-map to SDR
   and tag Rec.709 (1-1-1) on export — see [references/color-and-export.md](references/color-and-export.md).
8. **One subfolder per video — `videos/<name>/`.** Each video is fully self-contained
   (source, transcript, `config.py`, cut, stickers, `index.html`, render). Use the helper
   scripts (below) which take a `<name>`; never edit two videos' shared files. Do NOT copy the
   whole project per video — just make a new `videos/<name>/` via `edit/new.sh`.
9. **Generate ALL images fresh for each video; never recycle another video's stickers.** The
   sticker PNGs in `assets/stickers/` belong to the video they were made for. For a new video,
   regenerate every image from THAT transcript's mentions — do not reuse `claude.png`,
   `money-big.png`, etc. just because they exist. Reused, off-topic images are the #1 quality
   failure. If a brand/object recurs across videos, still re-generate (or deliberately re-map)
   it for the new context. **Use plenty of images — aim for ~20 per video** (a mix of company
   logos and concept/situation scenes); not sparse. Captions must still fit in the gaps.
10. **Every image is a CARTOON, but grounded in the REAL thing as a reference — never blind,
   never the plain logo.** Download the real asset first (brand logo, person's photo, flag,
   emblem) and feed it to `google/nano-banana-edit` as `image_urls` so the cartoon stays
   faithful (shape, colors, lettering, likeness). Plain downloaded logos read as "stock" and a
   blind `nano-banana` generation goes off-model — both got rejected. Scenes are allowed when a
   moment is an action/analogy: keep them to **1–3 cartoon characters**, same flat die-cut
   style. So: real brand → cartoon redraw of its logo; real person → cartoon of their photo;
   country → cartoon waving flag from the real flag; concept → minimal cartoon scene.

## Pipeline overview — per-video subfolders + helper scripts

Each video lives in `videos/<name>/`. Drive it with the scripts (all take `<name>`); the Python
builders read `videos/<name>/config.py` (per-video `SEGS`, `MENTIONS`, `TITLE`, `ACCENT`) and
write into that subfolder. **Preview is free; the slow render is only the final step.**

```
1. drop recording in inbox/        →  edit/new.sh <name>      (ingest + transcribe + scaffold config.py)
       new.sh transcribes with ElevenLabs Scribe (accurate proper nouns), --lang es by default.
       Override: edit/new.sh <name> --lang <code>. Whisper-small is only the fallback.
2. fill SEGS+MENTIONS+TITLE in videos/<name>/config.py ; generate FRESH stickers → videos/<name>/stickers/
3. edit/build.sh <name>            →  cut.mp4 + hairline + index.html   (FAST — no full render)
4. npm run dev                     →  preview videos/<name>/index.html in the studio (scrub/iterate)
5. edit/export.sh <name>           →  videos/<name>/<name>_REC709.mp4   (SLOW — only once approved)
6. upload it, then  edit/finish.sh <name>   →  delete everything for that video (manual)
```

`edit/build.sh` = `build_cut.py <name> --cut` → `detect_hairline.py <name>` → `build_comp.py <name>`.
Shared/reused across videos (not per-video): `assets/sfx/`, `music/` (drop tracks here),
`assets/stickers/gustavo.jpeg` + `gustavo-avatar.png`. Never hand-edit `index.html` (regenerated).

## Step 1 — Cut to the best takes

Input: `videos/<name>/transcript.json` (ElevenLabs Scribe via `edit/new.sh` — the only
transcriber). **First read the full transcript text**: find repeated lines
(keep the last clean take) AND spoken edit instructions ("Claude, elimínalo", "eso está mal, el
bueno es este") — drop the flub AND the instruction. ElevenLabs tags long pauses as
`audio_event`s, so they map every silence for you.

In `videos/<name>/config.py` (read by `build_cut.py <name>`) — **set the TIGHT knobs**:
- `SEGS` = list of `(first_word_start, last_word_start)` source-second blocks, retakes/instructions dropped.
- `PRE_PAD=0.04`, `POST_PAD=0.06`, `MAX_GAP=0.40` — cuts inter-phrase pauses, keeps intra-phrase rhythm (no jump cuts).
- `MAX_WORD_TAIL=0.60` — cap each word's effective end to trim trailing murmur/whisper.
- `CAPTION_FIXES` — `{lowercased_word: replacement}` for any residual mishears (e.g.
  `{"queed":"Qwen","kimi":"Kimi"}`); applied to captions by `build_comp.py`, timing untouched.
- `OUT_OVERRIDES` / `CUT_KILL` — hard out-points / cut-timeline ranges for stubborn tails.
- **Silence audit**: `build_cut.py` prints `max inter-word gap` + `gaps > MAX_GAP+0.05`. It MUST
  be **0** — if not, it lists each surviving pause; split the SEGS block at that pause.
- **Gaze audit**: extract a face crop every ~0.35s per segment (`crop=1000:1000:580:850`) and
  drop any sub-range where the speaker looks away (remove from `SEGS` or add a `CUT_KILL`).

Joints use 12ms audio fades to avoid clicks. Output is 1080×1920 **@60fps**, CRF 18, and the
HDR source is **tone-mapped HLG→SDR Rec.709 here** (needs a zscale ffmpeg — see
color-and-export.md). Run `python3 edit/build_cut.py <name>` (dry run, prints stats) then
`--cut` — or just `edit/build.sh <name>` for cut+hairline+index in one go.

See [references/cut-tuning.md](references/cut-tuning.md) for the exact knobs and the
energy-analysis recipe.

## Step 2 — Sticker images (synced, FRESH per video)

> **Generate every image fresh for this video** (Hard Rule 9). First read the transcript and
> list the moments worth an image — brands, objects, actions, analogies, named people — then
> create assets for *those*. Never assume an existing PNG fits; off-topic recycled images are
> the top complaint. Map each to the spoken word in `build_cut.py`'s
> `MENTIONS = [(src_word_start, sticker_id)]`, built from THIS transcript.

Image kinds:

- **Brand logos** → faithful cartoon. Download the real logo (Wikimedia
  `Special:FilePath/<File>.svg?width=600`, or GitHub org avatar
  `https://github.com/<org>.png?size=600`), upload to Kie, redraw with **`google/nano-banana-edit`**
  using the logo as `image_urls` reference.
- **Situations / actions / examples** → **multi-character cartoon scenes** (2–3 characters
  acting out the moment, e.g. "scientists shoveling money into a robot's head"). Generate with
  **`google/nano-banana`**. Whenever the speaker describes an action or analogy, make an image.
- **Real, named people** → **a real photo, NOT a cartoon** (Hard Rule 10). Fetch a portrait
  (Wikimedia `Special:FilePath/<Name>.jpg?width=600`, or an official source), frame it as a
  circle/rounded card with `scripts/make_avatar.py`. Do not cartoonize a real individual.

Place images **centered at chest height (y≈1400)**, adaptive size (explicit `width`+`height`,
`object-fit:contain` — never `height:auto`, the renderer stretches it), never over the face.
Each pop plays the **pop-click** SFX on the exact frame.

Style prompt, Kie endpoints, the 403/User-Agent workaround, the upload host, and background
keying (corner flood-fill, not u2net — preserves the white sticker border) are in
[references/sticker-pipeline.md](references/sticker-pipeline.md). Helper:
`scripts/key_sticker.py`.

## Step 3 — Compose (build_comp.py)

- **Title card**: persistent, **centered text**, two lines allowed, **square corners (no
  bevels)**, **dark liquid-glass** background (`rgba(3,4,7,.46)` + `backdrop-filter: blur(18px)
  saturate(125%)` + faint white rim — kept dark, not gray). Auto-fit base **66px** (0.75× the
  old 88px). Editable via the `title` composition variable.
  - **Vertical position is dynamic — measured per video, never hardcoded.** The card is
    centered in the band between the top of frame (y=0) and **where the hair starts**. Run
    `python3 edit/detect_hairline.py [cut.mp4]` → writes `edit/hairline.txt` (an int Y);
    `build_comp.py` reads it and sets `#title-card { height: <hairline>px }`. Re-run it for
    every video (different framing = different hairline) and **verify on a rendered frame that
    the card never touches the hair**. If detection looks off, set `edit/hairline.txt` by eye
    from an extracted frame.
- **Captions**: karaoke, chest zone, **mutually exclusive with stickers** (drop/trim any
  caption window that overlaps a sticker window + small guard). Current house style is
  **inverted**: no background box, black-filled letters with a 5px white outline
  (`-webkit-text-stroke` + `paint-order: stroke fill`); the active word is **green
  (`#487d00`) fill, white outline**, set as the `accent` variable. (Earlier style was a black
  pill with white text — both live in git history.)
- **Intro**: 1.3s zoom-out + fade-in on a non-timed `#intro-wrap` around the video; **camera
  shutter** SFX at 0.05s.
- **Stickers**: scale-pop in (`back.out(1.7)`), pop-click SFX, auto-truncate before the next
  mention.
- **Follow/CTA scene**: the user's circular avatar (`scripts/make_avatar.py` from a photo,
  white sticker ring) + `@handle` + a **CSS** SÍGUEME button (build the button in CSS, not as
  an AI sticker — AI sticker "paper" leaves an un-keyable white box).
- **Audio**: separate `<audio>` for the video's own track (volume 1) + a **music bed at
  −12 dB** (`volume = 10^(-12/20) ≈ 0.251`), full length, hard-cut at the end. SFX on their
  own track.

`TOTAL` is read from `edit/edl.json` so it always matches the cut.

## Step 4 — SFX & music

- Image pop: `assets/sfx/pop-click.mp3` (Mixkit "Hard pop click", #2364).
- Intro: `assets/sfx/camera.mp3` (Mixkit camera shutter).
- Source/audition more from Mixkit (free, no attribution): build an HTML audition page of
  candidates so the user picks by ear. Categories: golf, camera, pop, whoosh. Paste any
  `assets.mixkit.co/active_storage/sfx/<id>/<id>-preview.mp3` to add one.
- Music: drop tracks into `music/`; pick per video in `config.py` (`MUSIC = "music/track.mp3"`,
  default `music/background-music.mp3`, `""` = none) and `MUSIC_DB` (default -12). If quiet
  lines get buried, lower `MUSIC_DB` or offer speech-ducking.

## Step 5 — Build, PREVIEW, then export, QC

**Preview before rendering.** The full render is slow; don't run it to check the edit. Build
(fast) then scrub the live preview; only export once it's approved.

```bash
edit/build.sh <name>     # build_cut --cut + detect_hairline + build_comp  (FAST, no full render)
npm run check            # lint + validate + inspect — must pass
npm run dev              # preview: open videos/<name>/index.html in the studio (localhost:3002)
# iterate: edit videos/<name>/config.py or stickers → edit/build.sh <name> → refresh preview
edit/export.sh <name>    # ONLY once approved — render @60fps + 2-pass Rec.709 master (SLOW)
```
`export.sh` writes `videos/<name>/<name>_REC709.mp4` — the single universal **Rec.709 (1-1-1),
H.264 High, 60fps, AAC 48kHz** master. The HLG→SDR tone-map already happened in `build_cut.py`
(zscale + `hable`); see [references/color-and-export.md](references/color-and-export.md) (Chrome
`--sdr` alone washed out — don't use it as the tone-map).

QC the exported master: extract frames at the title, a caption-only beat, several sticker
beats, and the CTA, and **look at them**. Verify: face never covered; captions legible over
shirt and dark areas; glass title shows video through it; no caption under any sticker; **color
natural — not dark, not gray**. `ffprobe` must show `bt709` primaries/transfer/space,
`yuv420p`, `60/1`, `aac/48000/2`.

**Change the title without editing code:** `edit TITLE in videos/<name>/config.py`, or at
render: `npx hyperframes render -c videos/<name>/index.html --variables '{"title":"NUEVO"}' --fps 60 -o videos/<name>/out.mp4`

**Delete when done (manual):** `edit/finish.sh <name>` removes the whole `videos/<name>/`
(add `--keep-inputs` to keep source+transcript+config for a later re-edit).

## Project layout

```
inbox/                         # drop raw recordings here  (edit/new.sh picks them up)
videos/<name>/                 # one self-contained subfolder per video:
  source.MOV, transcript.json, config.py   # inputs (config = SEGS, MENTIONS, TITLE, ACCENT)
  edl.json, cut_words.json, mentions.json, hairline.txt, cut.mp4   # built
  stickers/<id>.png (+ raw/)   # FRESH per video; real people = real photo
  index.html, <name>_REC709.mp4
edit/                          # shared builders + scripts (new/build/export/finish, *.py)
assets/sfx/{pop-click,camera}.mp3 ; music/*.mp3 (drop tracks here)   # shared, reused
assets/stickers/gustavo.jpeg (+ gustavo-avatar.png)       # shared avatar
~/.local/bin/ffmpeg-tonemap    # zscale ffmpeg for HLG→SDR (see color-and-export.md)
.env → KIEAI_API_KEY           # Kie AI image generation
```

## Reference docs (load when needed)

- [references/cut-tuning.md](references/cut-tuning.md) — EDL knobs, silence/whisper RMS recipe, gaze audit.
- [references/sticker-pipeline.md](references/sticker-pipeline.md) — Kie AI endpoints + models, logo refs, prompts, keying.
- [references/composition-layout.md](references/composition-layout.md) — exact CSS/JS for title, captions, intro, follow scene, audio levels.
- [references/hyperframes-gotchas.md](references/hyperframes-gotchas.md) — clip-over-video rule and other traps.
- [references/color-and-export.md](references/color-and-export.md) — HDR→SDR fix, Rec.709 delivery spec, `export.sh`, color QC.
