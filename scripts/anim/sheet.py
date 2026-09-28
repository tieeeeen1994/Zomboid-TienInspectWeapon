#!/usr/bin/env python3
"""
Lay out x_preview.py's renders as one contact sheet: a row per view, a column per frame,
each labelled with its frame number. System python3 with Pillow:

    python3 scripts/anim/sheet.py <render_dir> <out.png> [frame,frame,...]

With a frame list only those frames are used (a clip rendered every 2 frames is too wide
for one sheet).
"""

import os
import re
import sys

from PIL import Image, ImageDraw


def main(src, out, only=None):
    shots = {}
    for name in os.listdir(src):
        m = re.match(r"(\w+?)_(\d+)\.png$", name)
        if m:
            shots.setdefault(m.group(1), {})[int(m.group(2))] = os.path.join(src, name)
    views = sorted(shots, key=lambda v: (v != "front", v))
    frames = sorted({f for v in views for f in shots[v]})
    if only:
        frames = [f for f in frames if f in only]
    w, h = Image.open(next(iter(shots[views[0]].values()))).size
    scale = 0.6
    tw, th = int(w * scale), int(h * scale)
    sheet = Image.new("RGB", (tw * len(frames), th * len(views)), (20, 20, 22))
    draw = ImageDraw.Draw(sheet)
    for r, v in enumerate(views):
        for c, f in enumerate(frames):
            if f in shots[v]:
                sheet.paste(Image.open(shots[v][f]).convert("RGB").resize((tw, th)), (c * tw, r * th))
            draw.text((c * tw + 6, r * th + 4), "%s f%d" % (v, f), fill=(230, 230, 230))
    sheet.save(out)
    print("[sheet]", out, sheet.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], {int(f) for f in sys.argv[3].split(",")} if len(sys.argv) > 3 else None)
