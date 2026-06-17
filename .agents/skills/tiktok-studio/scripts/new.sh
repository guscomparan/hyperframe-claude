#!/usr/bin/env bash
# Ingest a dropped recording into its own per-video subfolder, transcribe, scaffold config.
# Usage: edit/new.sh <name> [path/to/video]
#   - omit the path to auto-use the single file in inbox/
set -euo pipefail
cd "$(dirname "$0")/.."

# Usage: edit/new.sh <name> [video] [--lang <code>]
#   --lang defaults to "es" (this channel is Spanish). Use --lang auto to let whisper detect,
#   or another code (en, pt-br, ...). Auto-detect can mis-detect/translate short or quiet clips.
NAME=""; SRC=""; LANG_CODE="es"
while [ $# -gt 0 ]; do
  case "$1" in
    --lang) LANG_CODE="$2"; shift 2 ;;
    --lang=*) LANG_CODE="${1#*=}"; shift ;;
    *) if [ -z "$NAME" ]; then NAME="$1"; elif [ -z "$SRC" ]; then SRC="$1"; fi; shift ;;
  esac
done
[ -n "$NAME" ] || { echo "usage: edit/new.sh <name> [video] [--lang <code>]"; exit 1; }
BASE="videos/$NAME"
[ -e "$BASE" ] && { echo "videos/$NAME already exists — pick another name or 'edit/finish.sh $NAME' first."; exit 1; }

if [ -z "$SRC" ]; then
  shopt -s nullglob
  files=(inbox/*.MOV inbox/*.mov inbox/*.mp4 inbox/*.MP4)
  [ ${#files[@]} -eq 1 ] || { echo "Put exactly ONE video in inbox/ (found ${#files[@]}), or pass the path explicitly."; exit 1; }
  SRC="${files[0]}"
fi
[ -f "$SRC" ] || { echo "no such file: $SRC"; exit 1; }

mkdir -p "$BASE/stickers"
echo "[new] $SRC -> $BASE/source.MOV"
mv "$SRC" "$BASE/source.MOV"

# Transcribe with ElevenLabs Scribe — the ONLY transcription method for this project (accurate
# proper nouns + tags silences as audio_events). Whisper is NOT used: it mangles brand names.
# See scripts/transcribe_elevenlabs.py and references/cut-tuning.md.
SCRIBE="$(dirname "$0")/../.claude/skills/tiktok-studio/scripts/transcribe_elevenlabs.py"
declare -A L3=( [es]=spa [en]=eng [pt]=por [pt-br]=por [fr]=fra [de]=deu [it]=ita )
SLANG="${L3[$LANG_CODE]:-$LANG_CODE}"
[ -f "$SCRIBE" ] || { echo "ERROR: $SCRIBE missing."; exit 1; }
grep -q ELEVENLABS_API_KEY .env 2>/dev/null || { echo "ERROR: ELEVENLABS_API_KEY missing from .env (required — Scribe is the only transcriber)."; exit 1; }
echo "[new] transcribing (ElevenLabs Scribe, $SLANG)..."
python3 "$SCRIBE" "$BASE/source.MOV" "$BASE" "$SLANG" || { echo "ERROR: Scribe transcription failed — fix it and re-run (no whisper fallback)."; exit 1; }
[ -f "$BASE/transcript.json" ] || { echo "ERROR: transcript.json not found in $BASE."; exit 1; }

cp edit/config.template.py "$BASE/config.py"
echo "[new] ready: $BASE/ (source.MOV, transcript.json, config.py, stickers/)"
echo
echo "Next:"
echo "  1. Fill SEGS + MENTIONS + TITLE in $BASE/config.py (use /tiktok-studio)."
echo "  2. Generate fresh stickers into $BASE/stickers/ for each MENTIONS id."
echo "  3. edit/build.sh $NAME        # cut + index.html (fast, no full render)"
echo "  4. npm run dev                # preview $BASE/index.html in the studio"
echo "  5. edit/export.sh $NAME       # final Rec.709 master (slow)"
echo "  6. edit/finish.sh $NAME       # delete everything when you're done (manual)"
