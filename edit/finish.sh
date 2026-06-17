#!/usr/bin/env bash
# Delete EVERYTHING for a finished video (manual — run only when YOU say so, after uploading).
# Usage: edit/finish.sh <name> [--keep-inputs]
#   default       : remove the whole videos/<name>/ folder (source + cut + stickers + render).
#   --keep-inputs : keep source.MOV + transcript.json + config.py, delete the rest.
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?usage: edit/finish.sh <name> [--keep-inputs]}"
BASE="videos/$NAME"
[ -d "$BASE" ] || { echo "no videos/$NAME"; exit 1; }

if [ "${2:-}" = "--keep-inputs" ]; then
  echo "[finish] keeping source.MOV + transcript.json + config.py; deleting the rest of $BASE"
  find "$BASE" -mindepth 1 -maxdepth 1 \
    ! -name source.MOV ! -name transcript.json ! -name config.py -exec rm -rf {} +
  echo "[finish] kept inputs in $BASE — re-run edit/build.sh $NAME to rebuild later."
else
  du -sh "$BASE" 2>/dev/null
  rm -rf "$BASE"
  echo "[finish] removed $BASE (left no trace)."
fi
