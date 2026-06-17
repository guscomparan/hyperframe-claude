#!/usr/bin/env python3
"""High-accuracy transcription via ElevenLabs Scribe — USE THIS, not whisper-small.

Whisper-small mangles every proper noun (Claude->"Cloth", Anthropic->"Antropi",
DeepSeek->"Dipsick", Qwen->"Juan", Ascend->"Ascent"), which poisons captions AND makes the
cut hard to reason about. Scribe gets brand names right and, crucially, tags every long
silence as an `audio_event` ("(pausa de N segundos)") so you can SEE where the pauses are.

Usage:  transcribe_elevenlabs.py <source.MOV|audio.mp3> <out_dir> [lang=spa]
Writes: <out_dir>/transcript.json   (ElevenLabs shape: {"words":[{text,start,end,type}]},
        which build_cut.py already accepts). Needs ELEVENLABS_API_KEY in the repo-root .env.
"""
import json, os, subprocess, sys, tempfile, urllib.request

if len(sys.argv) < 3:
    raise SystemExit("usage: transcribe_elevenlabs.py <source> <out_dir> [lang=spa]")
SRC, OUT_DIR = sys.argv[1], sys.argv[2]
LANG = sys.argv[3] if len(sys.argv) > 3 else "spa"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
KEY = next((l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env"))
            if l.startswith("ELEVENLABS_API_KEY")), None)
if not KEY:
    raise SystemExit("ELEVENLABS_API_KEY missing from .env")

# Extract a small mono 16k mp3 (the MOV is huge; Scribe only needs audio).
audio = SRC
tmp = None
if not SRC.lower().endswith((".mp3", ".wav", ".m4a")):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vn", "-ac", "1", "-ar", "16000",
                    "-b:a", "64k", "-y", tmp], check=True)
    audio = tmp

# multipart/form-data POST (stdlib only)
boundary = "----hfscribe"
def part(name, value):
    return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode()
body = part("model_id", "scribe_v1") + part("language_code", LANG)
body += part("timestamps_granularity", "word") + part("diarize", "false")
fdata = open(audio, "rb").read()
body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp3\"\r\n"
         f"Content-Type: audio/mpeg\r\n\r\n").encode() + fdata + f"\r\n--{boundary}--\r\n".encode()
req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body,
                             headers={"xi-api-key": KEY, "Content-Type": f"multipart/form-data; boundary={boundary}"},
                             method="POST")
print(f"[scribe] transcribing {os.path.basename(SRC)} ({LANG})...")
d = json.load(urllib.request.urlopen(req, timeout=600))
if tmp:
    os.unlink(tmp)
os.makedirs(OUT_DIR, exist_ok=True)
json.dump(d, open(os.path.join(OUT_DIR, "transcript.json"), "w"), ensure_ascii=False, indent=1)
words = [w for w in d.get("words", []) if w.get("type") == "word"]
pauses = [w for w in d.get("words", []) if w.get("type") == "audio_event"]
print(f"[scribe] {len(words)} words, {len(pauses)} pause/audio events, "
      f"{d.get('audio_duration_secs', 0):.0f}s -> {OUT_DIR}/transcript.json")
print("[scribe] NOTE: read the full text and listen for spoken edit instructions "
      "('elimínalo', 'eso está mal', 'el bueno es este') — cut those + their flubbed take.")
