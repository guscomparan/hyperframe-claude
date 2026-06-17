#!/usr/bin/env python3
"""Detect where the subject's hair starts (topmost hair row) across the cut, so the title
band is positioned PER VIDEO — never a hardcoded Y. Writes videos/<name>/hairline.txt (an int
Y in the 1080x1920 frame). The title is centered between the top of frame (0) and this value.

Usage: detect_hairline.py <name>
Heuristic — ALWAYS verify on a preview/rendered frame that the title never touches the hair.
"""
import os, subprocess, sys, tempfile
from PIL import Image

if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
    raise SystemExit("usage: detect_hairline.py <name>")
NAME = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "videos", NAME)
VIDEO = os.path.join(BASE, "cut.mp4")

dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", VIDEO], capture_output=True, text=True).stdout or 60)

tops = []
for frac in (0.05, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
    p = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur*frac:.2f}", "-i", VIDEO,
                    "-frames:v", "1", "-y", p], check=True)
    im = Image.open(p).convert("RGB"); W, H = im.size; px = im.load()
    for y in range(0, H // 2, 4):                       # scan top→down
        # count dark pixels across the central band (hair sits center-top)
        dark = sum(1 for x in range(int(W * 0.30), int(W * 0.70), 6) if sum(px[x, y]) < 240)
        if dark >= 8:
            tops.append(y)
            break
    os.remove(p)

# use the HIGHEST the hair reaches (min Y) so the title never overlaps at any moment;
# small safety margin; sane floor.
hair = max((min(tops) if tops else 520) - 12, 120)
open(os.path.join(BASE, "hairline.txt"), "w").write(str(hair))
print(f"[{NAME}] hairline_y = {hair}   (samples: {sorted(tops)})")
