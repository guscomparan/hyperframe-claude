#!/usr/bin/env bash
# Final delivery: render videos/<name>/index.html @60fps, then 2-pass H.264 Rec.709 master.
# Run only AFTER you've previewed and approved (this is the slow step).
# Usage: edit/export.sh <name> [bitrate]   (default bitrate 16M)
#
# Color: the HLG->SDR tone-map already happened in build_cut.py (zscale+hable), so the cut is
# SDR Rec.709 and this just 2-pass-encodes tagged Rec.709 (1-1-1), yuv420p, 60fps, AAC 48kHz.
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?usage: edit/export.sh <name> [bitrate]}"
BITRATE="${2:-16M}"
BASE="videos/$NAME"
[ -f "$BASE/index.html" ] || { echo "no $BASE/index.html — run edit/build.sh $NAME first."; exit 1; }
SDR="$BASE/render_sdr.mp4"
OUT="$BASE/${NAME}_REC709.mp4"

echo "[1/3] Rendering @60fps (cut is already SDR Rec.709)..."
npx --yes hyperframes@0.6.88 render -c "$BASE/index.html" --quiet --fps 60 -o "$SDR"

echo "[2/3] 2-pass H.264 delivery encode (Rec.709 1-1-1, ${BITRATE}, 60fps, AAC 48k)..."
PASSLOG="$(mktemp -t x264pass)"
VF="format=yuv420p"
COLOR=(-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv)
X264P="colorprim=bt709:transfer=bt709:colormatrix=bt709"
ffmpeg -y -i "$SDR" -vf "$VF" -r 60 -c:v libx264 -profile:v high -preset slow -b:v "$BITRATE" \
  -x264-params "${X264P}:pass=1:stats=${PASSLOG}" "${COLOR[@]}" -an -f mp4 /dev/null
ffmpeg -y -i "$SDR" -vf "$VF" -r 60 -c:v libx264 -profile:v high -preset slow -b:v "$BITRATE" \
  -x264-params "${X264P}:pass=2:stats=${PASSLOG}" "${COLOR[@]}" \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$OUT"
rm -f "${PASSLOG}"* "$SDR"

echo "[3/3] Verifying..."
ffprobe -v error -select_streams v:0 -show_entries \
  stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,color_space,color_primaries,color_transfer,color_range \
  -of default=noprint_wrappers=1 "$OUT"
echo "Done -> $OUT   (upload this; then: edit/finish.sh $NAME)"
