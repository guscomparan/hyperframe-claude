#!/usr/bin/env bash
# Build a video's composition for PREVIEW (no full render): cut + hairline + index.html.
# Usage: edit/build.sh <name>
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?usage: edit/build.sh <name>}"
BASE="videos/$NAME"
[ -d "$BASE" ] || { echo "no videos/$NAME — run edit/new.sh $NAME first."; exit 1; }

echo "[build] cut (HLG->SDR tone-map, 60fps)..."
python3 edit/build_cut.py "$NAME" --cut
echo "[build] hairline (title position)..."
python3 edit/detect_hairline.py "$NAME"
echo "[build] index.html..."
python3 edit/build_comp.py "$NAME"
echo
echo "Preview it:  npm run dev   ->  open $BASE/index.html in the studio (localhost:3002)"
echo "When happy:  edit/export.sh $NAME   (final Rec.709 master)"
