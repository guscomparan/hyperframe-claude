#!/usr/bin/env python3
"""Detect the subject's HEAD extents across the cut, so overlays never block the head — per
video, never hardcoded. Writes two ints (in the 1080x1920 authoring space):
  videos/<name>/hairline.txt  — topmost hair row (title band = 0..hairline; title sits above it)
  videos/<name>/chin.txt      — a safe FLOOR below the chin (stickers' top edge must stay below
                                it so images never touch/block the chin at any moment)

Usage: detect_head_bounds.py <name>
Heuristic — ALWAYS verify on a preview/rendered frame that NO overlay touches the hair or chin.
"""
import os, subprocess, sys, tempfile
from PIL import Image

if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
    raise SystemExit("usage: detect_head_bounds.py <name>")
NAME = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "videos", NAME)
VIDEO = os.path.join(BASE, "cut.mp4")

dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", VIDEO], capture_output=True, text=True).stdout or 60)

def is_skin(c):
    r, g, b = c
    return (r > 95 and g > 40 and b > 20 and (max(c) - min(c)) > 15
            and abs(r - g) > 15 and r > g and r > b)

def analyze(px, W, H):
    """Return (hair_top, chin_neck) for one frame, both in this frame's pixel space."""
    # hair top: first row (top→down) with enough dark pixels across the central band
    hair = 120
    for y in range(0, H // 2, 4):
        if sum(1 for x in range(int(W * 0.30), int(W * 0.70), 6) if sum(px[x, y]) < 240) >= 8:
            hair = y
            break
    # face center x = centroid of forehead skin (just below the hairline)
    fx = [x for y in range(hair + 50, hair + 150, 4)
          for x in range(int(W * 0.25), int(W * 0.75), 4) if is_skin(px[x, y])]
    cx = sum(fx) // len(fx) if fx else W // 2
    # width of the contiguous skin/hair run around the face center, per row (search bounded to
    # ±0.28W so gesturing hands at chest don't widen it). The head/jaw is the widest part; the
    # NECK just under the chin is the narrowest run below the peak — a reliable "below the chin"
    # anchor (more robust than trying to detect the chin contour directly).
    lim = int(W * 0.28)
    prof = []
    for y in range(hair, min(int(H * 0.62), 1180), 4):
        def fg(xx):
            xx = min(max(xx, 0), W - 1)
            return is_skin(px[xx, y]) or sum(px[xx, y]) < 240   # skin OR dark hair/shadow
        L = cx
        while L > cx - lim and fg(L):
            L -= 3
        R = cx
        while R < cx + lim and fg(R):
            R += 3
        prof.append((y, R - L))
    ws = [w for _, w in prof]
    y_peak = prof[ws.index(max(ws))][0]
    below = [(y, w) for y, w in prof if y > y_peak + 30]
    neck = min(below, key=lambda t: t[1])[0] if below else y_peak
    return hair, neck

hairs, necks, frame_h = [], [], 1920
for frac in (0.05, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 0.2, 0.5):
    p = tempfile.mktemp(suffix=".png")
    # extract scaled to the 1080x1920 authoring space (detection is calibrated there)
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * frac:.2f}", "-i", VIDEO,
                    "-frames:v", "1", "-vf", "scale=1080:1920", "-y", p], check=True)
    im = Image.open(p).convert("RGB"); W, H = im.size; frame_h = H
    h, n = analyze(im.load(), W, H)
    hairs.append(h); necks.append(n)
    os.remove(p)

# hairline: the HIGHEST the hair reaches (min Y) so the title never overlaps; small safety margin.
hair = max((min(hairs) if hairs else 520) - 12, 120)
# chin floor: the LOWEST the chin/neck reaches (max Y) + margin, so stickers clear the chin even
# when the subject leans forward. Clamp to a sane band: never higher than the legacy 1120 floor
# (don't push stickers up into the head), never below 1320 (keep them on the chest).
chin = min(max((max(necks) if necks else 1140) + 40, 1120), 1320)
open(os.path.join(BASE, "hairline.txt"), "w").write(str(hair))
open(os.path.join(BASE, "chin.txt"), "w").write(str(chin))
print(f"[{NAME}] hairline_y = {hair}  (hair samples: {sorted(hairs)})")
print(f"[{NAME}] chin_floor = {chin}  (neck samples: {sorted(necks)})")
