# Color & export — fix HDR-source darkness, deliver Rec.709

## The problem (always check this)

The user's iPhone footage is **HDR**: HEVC 10-bit, `color_primaries=bt2020`,
`color_transfer=arib-std-b67` (HLG), often with Dolby Vision RPU. If that HDR is not
**properly** tone-mapped to SDR before delivery:

- **Instagram / Facebook** show it **too dark / shadowed** (they don't tone-map the HDR).
- **TikTok** (historically) showed it **washed-out / gray**.

Symptom-to-cause: a "shadow over the whole video" or "everything looks gray/flat" on upload is
an HDR→SDR problem, not exposure. **Always `ffprobe` the source and any render first:**

```bash
ffprobe -v error -select_streams v:0 -show_entries \
  stream=codec_name,pix_fmt,color_space,color_primaries,color_transfer,color_range,r_frame_rate \
  -of default=noprint_wrappers=1 <file>
```
`bt2020` / `arib-std-b67` (HLG) / `smpte2084` (PQ) / `yuv420p10le` ⇒ HDR.

## What does NOT work (learned the hard way)

- **`hyperframes render --sdr` (Chrome tone-map) alone** → comes out **washed / low-contrast /
  raised blacks**. Browsers don't apply the HLG OOTF system gamma, so the SDR looks flat. Not
  acceptable.
- **ffmpeg `tonemap` without linearization** (`format=gbrpf32le,tonemap=...`) → comes out
  **too dark**. `tonemap` needs linear-light input, which requires `zscale`.
- **Stock Homebrew ffmpeg** has **no `zscale` and no `libplacebo`** (`ffmpeg -filters | grep
  zscale` is empty), so it can't do a correct HLG tone-map at all.

## The fix — tone-map at the cut with a zscale ffmpeg

1. **Get a zscale-capable ffmpeg** (no slow compile). Static macOS arm64 build:
   ```bash
   curl -sL "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip" -o /tmp/ff.zip
   unzip -o /tmp/ff.zip -d /tmp/ffstatic && cp /tmp/ffstatic/ffmpeg ~/.local/bin/ffmpeg-tonemap
   chmod +x ~/.local/bin/ffmpeg-tonemap
   ~/.local/bin/ffmpeg-tonemap -filters | grep zscale   # must print zscale
   ```
   `build_cut.py` auto-uses `~/.local/bin/ffmpeg-tonemap` (or `$FFMPEG_TONEMAP`) and errors if
   zscale is missing.
2. **Tone-map HLG→SDR Rec.709 in the cut** (proper linearize → tonemap → re-encode 709). This
   build of the chain is in `build_cut.py` as `TONEMAP`:
   ```
   zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:p=bt709:r=tv,format=yuv420p
   ```
   `hable` (filmic) gave the best highlight rolloff for the bright window; `mobius`/`reinhard`
   are alternatives. The cut is then a true **SDR Rec.709, 8-bit, 60fps** file tagged
   `bt709/bt709/bt709`, range tv. Because the cut is already SDR, the HyperFrames render is SDR
   automatically (no `--sdr` needed).
3. **Deliver Rec.709 (1-1-1), 2-pass H.264**, matching the user's Final Cut spec:
   - MP4 ("Computer"), `+faststart`; H.264 **High**, **2-pass** ("Multi-pass / Better");
     1080×1920; 8-bit `yuv420p`
   - Color: `colorprim=bt709:transfer=bt709:colormatrix=bt709`, `color_range tv`
   - **60 fps** (source is 60fps; cut + render at 60); Audio **AAC 48 kHz stereo**

One correctly-tone-mapped Rec.709 file is the universal master for **YouTube, TikTok,
Instagram, Facebook**.

## One-command export

`edit/export.sh [name] [bitrate]` renders the (already-SDR) cut at 60fps, then 2-pass-encodes
the Rec.709 master and prints the tags. Defaults: `distillation-tiktok`, `16M`.

```bash
edit/export.sh                 # -> renders/distillation-tiktok_REC709.mp4
edit/export.sh my-video 10M
```

## QC (mandatory)

- `ffprobe` the master: `color_primaries/transfer/space=bt709`, `pix_fmt=yuv420p`,
  `r_frame_rate=60/1`, audio `aac/48000/2`, no mastering-display/CLL/Dolby side-data.
- Extract frames and **look**: skin natural, greens vivid, window highlights controlled —
  **not dark/shadowed, not flat/gray**. Compare against how the HDR source looks tone-mapped by
  QuickTime (that OS tone-map is the target appearance).
