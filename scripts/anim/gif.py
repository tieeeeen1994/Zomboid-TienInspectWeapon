#!/usr/bin/env python3
"""
Turn x_preview.py's renders into a looping animated GIF, the views side by side, played
at the clip's real speed. System python3 with Pillow:

    python3 scripts/anim/gif.py <render_dir> <out.gif> [step] [scale]

[step] is the frame step the renders were made with (x_preview.py ... every:2 -> 2,
the default); each GIF frame then lasts step/30 s. For a looping clip whose last frame
equals its first, the last is dropped so the loop does not stutter.
"""

import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw


def main(src, out, step=2, scale=0.7):
    shots = {}
    for name in os.listdir(src):
        m = re.match(r"(\w+?)_(\d+)\.png$", name)
        if m:
            shots.setdefault(int(m.group(2)), {})[m.group(1)] = os.path.join(src, name)
    frames = sorted(shots)
    views = sorted(shots[frames[0]], key=lambda v: (v != "front", v))
    w, h = Image.open(shots[frames[0]][views[0]]).size
    images = []
    for f in frames:
        img = Image.new("RGB", (w * len(views), h))
        for i, v in enumerate(views):
            img.paste(Image.open(shots[f][v]).convert("RGB"), (i * w, 0))
        if scale != 1:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        images.append(img)
    if len(images) > 2 and ImageChops.difference(images[0], images[-1]).getbbox() is None:
        images.pop()
        frames.pop()
    for f, img in zip(frames, images):
        ImageDraw.Draw(img).text((8, 6), "frame %d" % f, fill=(230, 230, 230))
    images[0].save(out, save_all=True, append_images=images[1:], loop=0,
                   duration=int(1000 * step / 30.0), optimize=True)
    print("[gif]", out, len(images), "frames")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2,
         float(sys.argv[4]) if len(sys.argv) > 4 else 0.7)
