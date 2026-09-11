#!/usr/bin/env python3
"""
Art for Tien's Weapon Inspection.

Everything the mod ships as an image is drawn here rather than kept as a binary nobody
can edit: the Workshop poster, the mod.info icon and the repository preview. Run it from
the repository root:

    python3 scripts/make_art.py

The subject is the mod in one picture - a blade held up to be looked over, with the
condition bars the window draws beside it - in Project Zomboid's own palette: near-black
ground, desaturated steel, and the amber the game uses for anything worth reading.
"""

import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "Contents", "mods", "TienInspectWeapon", "42")

BG_TOP = (26, 28, 31)
BG_BOTTOM = (14, 15, 17)
STEEL_DARK = (104, 112, 122)
STEEL = (168, 178, 190)
STEEL_HI = (222, 230, 238)
HANDLE = (74, 54, 38)
HANDLE_HI = (104, 78, 56)
AMBER = (214, 158, 62)
GOOD = (110, 176, 92)
WORN = (206, 150, 60)
BAD = (188, 74, 58)
INK = (232, 236, 240)
MUTED = (128, 136, 146)

# The canvas is drawn large and reduced at the end; every edge in it is a straight line
# or a circle, and both alias badly at 128 pixels unless they were 512 first.
SS = 4


def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((w, h), Image.BILINEAR)


def vignette(img, strength=0.55):
    """Darken the corners, which is what stops a flat panel reading as a flat panel."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w * 0.22, -h * 0.22, w * 1.22, h * 1.22], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w * 0.10))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, Image.blend(img, dark, strength), mask)


def draw_blade(d, cx, cy, length, width):
    """
    A machete held point-up, tilted the way a hand holds something being looked at.

    Drawn as three polygons - back edge, cutting edge, highlight - so the bevel reads
    as a bevel rather than as a grey rectangle with a line down it.
    """
    tilt = 0.18
    tip = (cx + length * tilt, cy - length * 0.52)
    guard = (cx - length * tilt * 0.55, cy + length * 0.16)

    def along(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    spine_off = width * 0.5
    edge_off = -width * 0.5
    shoulder = along(guard, tip, 0.76)

    def offset(p, dx):
        return (p[0] + dx, p[1])

    # Body of the blade: full width from the guard to the shoulder, then in to the tip.
    d.polygon([
        offset(guard, spine_off),
        offset(shoulder, spine_off),
        offset(tip, spine_off * 0.10),
        offset(tip, edge_off * 0.10),
        offset(shoulder, edge_off * 1.10),
        offset(guard, edge_off),
    ], fill=STEEL)

    # The flat back of the blade catches less light than the ground bevel.
    d.polygon([
        offset(guard, spine_off),
        offset(shoulder, spine_off),
        offset(tip, spine_off * 0.10),
        offset(tip, spine_off * 0.02),
        offset(shoulder, spine_off * 0.42),
        offset(guard, spine_off * 0.42),
    ], fill=STEEL_DARK)

    # The bevel itself, the brightest thing in the picture.
    d.polygon([
        offset(guard, edge_off * 0.46),
        offset(shoulder, edge_off * 0.52),
        offset(tip, edge_off * 0.08),
        offset(tip, edge_off * 0.10),
        offset(shoulder, edge_off * 1.10),
        offset(guard, edge_off),
    ], fill=STEEL_HI)

    # Guard, then handle running down out of frame.
    g0 = along(guard, tip, -0.02)
    d.polygon([
        (g0[0] - width * 0.82, g0[1]),
        (g0[0] + width * 0.82, g0[1]),
        (g0[0] + width * 0.74, g0[1] + width * 0.34),
        (g0[0] - width * 0.74, g0[1] + width * 0.34),
    ], fill=STEEL_DARK)

    h0 = (g0[0], g0[1] + width * 0.34)
    h1 = (cx - length * tilt * 0.95, cy + length * 0.52)
    d.polygon([
        (h0[0] - width * 0.46, h0[1]),
        (h0[0] + width * 0.46, h0[1]),
        (h1[0] + width * 0.40, h1[1]),
        (h1[0] - width * 0.40, h1[1]),
    ], fill=HANDLE)
    d.polygon([
        (h0[0] - width * 0.46, h0[1]),
        (h0[0] - width * 0.12, h0[1]),
        (h1[0] - width * 0.08, h1[1]),
        (h1[0] - width * 0.40, h1[1]),
    ], fill=HANDLE_HI)


def draw_readout(d, x, y, w, rows, bar_h, gap):
    """The window's own bars, which is what the mod actually puts on screen."""
    for i, (frac, color) in enumerate(rows):
        by = y + i * (bar_h + gap)
        d.rectangle([x, by, x + w, by + bar_h], fill=(38, 41, 45))
        d.rectangle([x, by, x + w * frac, by + bar_h], fill=color)
        d.rectangle([x, by, x + w, by + bar_h], outline=(72, 78, 85), width=max(1, int(bar_h // 9)))


def compose(size, with_bars=True, margin_scale=1.0):
    s = size * SS
    img = vertical_gradient((s, s), BG_TOP, BG_BOTTOM)
    d = ImageDraw.Draw(img)

    # A faint circle behind the blade, the way an inspection screen frames its subject.
    r = s * 0.40
    d.ellipse([s * 0.5 - r, s * 0.5 - r, s * 0.5 + r, s * 0.5 + r], outline=(44, 48, 53),
              width=max(1, int(s * 0.006)))

    blade_cx = s * (0.33 if with_bars else 0.5)
    draw_blade(d, blade_cx, s * 0.48, s * 0.72 * margin_scale, s * 0.135 * margin_scale)

    if with_bars:
        bar_x = s * 0.60
        bar_w = s * 0.30
        bar_h = s * 0.048
        gap = s * 0.055
        draw_readout(d, bar_x, s * 0.34, bar_w,
                     [(0.82, GOOD), (0.46, WORN), (0.17, BAD)], bar_h, gap)
        # Labels are bars too at this size: a legible word would be three pixels tall.
        for i in range(3):
            ly = s * 0.34 + i * (bar_h + gap) - bar_h * 0.78
            d.rectangle([bar_x, ly, bar_x + bar_w * (0.52 - i * 0.10), ly + bar_h * 0.26],
                        fill=MUTED)

    img = vignette(img)
    return img.resize((size, size), Image.LANCZOS)


def main():
    poster = compose(512)
    poster.save(os.path.join(MOD, "poster.png"))
    poster.save(os.path.join(ROOT, "preview.png"))

    # The icon is seen at the size of a mod list row, so the bars are dropped and the
    # blade is given the whole frame.
    compose(128, with_bars=False, margin_scale=0.92).save(os.path.join(MOD, "icon.png"))

    for p in ("poster.png", "icon.png"):
        print("wrote", os.path.join(MOD, p))
    print("wrote", os.path.join(ROOT, "preview.png"))


if __name__ == "__main__":
    main()
