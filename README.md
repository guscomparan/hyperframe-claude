# TikTok Studio — reusable editor

One repo, many videos. Each video lives in its own `videos/<name>/` subfolder, so they never
collide. Drop a recording in `inbox/`, edit it, preview it, export the master, upload, then
delete it — no leftover files. Driven by the **`/tiktok-studio`** skill.

## Workflow

```bash
# 1. Drop your recording into  inbox/   (e.g. inbox/IMG_2501.MOV)

# 2. Ingest it into its own subfolder + transcribe + scaffold config
#    (transcribes in Spanish by default; use --lang <code> or --lang auto to change)
edit/new.sh myvideo

# 3. Fill videos/myvideo/config.py  (SEGS = best takes, MENTIONS = images, TITLE)
#    and generate FRESH stickers into videos/myvideo/stickers/   (use /tiktok-studio)

# 4. Build for preview — FAST, no full render
edit/build.sh myvideo

# 5. Preview in the browser and iterate (re-run build.sh after edits)
npm run dev            # open videos/myvideo/index.html in the studio (localhost:3002)

# 6. Happy? Render the final upload master — SLOW, run once
edit/export.sh myvideo            # -> videos/myvideo/myvideo_REC709.mp4

# 7. Upload it, then delete everything for that video (manual, only when you say so)
edit/finish.sh myvideo            # add --keep-inputs to keep source+transcript+config
```

Preview is free — you do **not** need to render to review the edit. The slow render/export is
only for the final upload file.

## What's shared vs per-video

- **Shared (reused by every video):** `edit/` builders & scripts, `assets/sfx/`, `music/`
  (drop tracks here), `assets/stickers/gustavo.jpeg` (+ generated `gustavo-avatar.png`),
  `.env` (`KIEAI_API_KEY`), and the `/tiktok-studio` skill.

## Music

Default track is `music/background-music.mp3` at −12 dB. Drop more tracks into `music/`, then
pick one per video in `videos/<name>/config.py`:
```python
MUSIC = "music/my-other-track.mp3"   # default: music/background-music.mp3 ;  "" = no music
MUSIC_DB = -12                       # lower = quieter
```
- **Per-video (in `videos/<name>/`):** source, transcript, `config.py`, cut, stickers,
  `index.html`, and the exported master. `finish.sh` deletes this whole folder.

Source `.MOV`s, cuts, renders, transcripts, and generated stickers are git-ignored (large /
regenerated). Keep your original recordings backed up outside the repo.

## Requirements

- `~/.local/bin/ffmpeg-tonemap` — a zscale-capable ffmpeg for the HLG→SDR tone-map (the iPhone
  source is HDR). See the skill's `references/color-and-export.md` for the one-line install.
- `.env` with `KIEAI_API_KEY` for image generation.
