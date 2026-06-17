# Per-video edit config — fill from THIS video's transcript.
# See the tiktok-studio skill: references/cut-tuning.md + references/sticker-pipeline.md.

TITLE = "TÍTULO DEL VIDEO"   # glass title card text (also editable at render via --variables)
ACCENT = "#487d00"           # karaoke highlight color
FOLLOW_HANDLE = "@tuusuario"  # your @handle for the SÍGUEME / follow CTA scene
# FOLLOW_AVATAR = "assets/stickers/gustavo-avatar.png"  # swap in your own avatar (regen from your photo)

# Music: a file under music/ (root-relative path). Default = the shared track.
# Drop more tracks into music/ and point MUSIC at one. Set MUSIC = "" for no music.
MUSIC = "music/background-music.mp3"
MUSIC_DB = -12               # music level in dB (-12 default; lower = quieter)

# Silence removal — TIGHT defaults (no pause/silence should survive). Loosen only if choppy.
PRE_PAD = 0.04
POST_PAD = 0.06
MAX_GAP = 0.40               # cuts inter-phrase pauses; DON'T go lower (0.22/0.30 jump-cut mid-phrase)
MAX_WORD_TAIL = 0.60         # cap held final syllables / trailing murmur
# After build_cut.py, the silence audit MUST print "0 gap(s) > ...".

# (first_word_start, last_word_start) per kept block, in SOURCE seconds.
# Keep the LAST clean take of each line; DROP retakes/false starts AND spoken edit instructions
# ("Claude, elimínalo", "eso está mal, el bueno es este").
SEGS = [
    # (0.28, 13.66),
]

# (src_word_start, sticker_id) — FRESH per video. Cartoon images grounded in the REAL asset as
# a nano-banana-edit reference (logo/photo/flag) — never the plain logo, never blind generation.
MENTIONS = [
    # (3.11, "anthropic"),
]

# Caption text fixes for residual transcription mishears in KEPT blocks (matches audio):
CAPTION_FIXES = {
    # "queed": "Qwen", "kimi": "Kimi",
}

# Optional fine-tuning (leave empty unless needed):
OUT_OVERRIDES = {}   # {last_word_start: hard_src_out}  — trim a stubborn trailing tail
CUT_KILL = []        # [(cut_start, cut_end)]  — RMS-verified whisper/dead-air windows to cut
