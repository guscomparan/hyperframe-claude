#!/usr/bin/env python3
"""Key a flat-cartoon sticker's background by corner flood-fill, preserving the white
die-cut border (which u2net would eat). Usage: key_sticker.py <raw.png> <out.png> [tol]"""
import sys
from collections import deque
from PIL import Image, ImageFilter

def key_bg(src, dst, tol=28):
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    px = im.load()
    ref = px[0, 0][:3]
    mask = [[False] * w for _ in range(h)]
    q = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
               (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)])
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or mask[y][x]:
            continue
        c = px[x, y][:3]
        if abs(c[0] - ref[0]) + abs(c[1] - ref[1]) + abs(c[2] - ref[2]) > tol * 3:
            continue
        mask[y][x] = True
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                ap[x, y] = 0
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(alpha)
    im = im.crop(im.getbbox())
    im.save(dst)
    return im.size

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    tol = int(sys.argv[3]) if len(sys.argv) > 3 else 28
    print(key_bg(src, dst, tol))
