#!/usr/bin/env python3
"""Circular avatar with a white sticker ring from a photo, for the follow/CTA scene.
Usage: make_avatar.py <photo.jpg> <out.png> [diameter]"""
import sys
from PIL import Image, ImageDraw

def make(src, dst, D=600, ring=26):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((D, D), Image.LANCZOS)
    canvas = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    photo = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    m = Image.new("L", (D, D), 0)
    ImageDraw.Draw(m).ellipse((ring, ring, D - ring, D - ring), fill=255)
    photo.paste(im, (0, 0)); photo.putalpha(m)
    rd = ImageDraw.Draw(canvas)
    rd.ellipse((2, 2, D - 2, D - 2), fill=(20, 24, 32, 255))      # dark outline
    rd.ellipse((6, 6, D - 6, D - 6), fill=(255, 255, 255, 255))   # white ring
    canvas.alpha_composite(photo)
    canvas.save(dst)
    return canvas.size

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    D = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    print(make(src, dst, D))
