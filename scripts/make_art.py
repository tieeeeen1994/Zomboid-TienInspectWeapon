#!/usr/bin/env python3
"""
Art for Tien's Weapon Inspection.

Everything the mod ships as an image is built here rather than kept as a binary nobody
can edit: the Workshop poster, the mod.info icon and the repository preview. Run it from
the repository root, with Project Zomboid installed:

    python3 scripts/make_art.py

The subject is the mod in one picture - a weapon held up to be looked over, with the
condition bars the window draws beside it.

The weapon and the magnifier are the game's own art, read out of the install at build
time rather than redrawn or committed here. A mod's icon sitting in the mod list next to
vanilla's own is better off looking like it belongs there, and a hand-drawn approximation
of a machete only ever looks like an approximation of a machete. Nothing extracted is
written to this repository - only the composite - so the game's files stay where they are.
"""

import io
import os
import re
import struct
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "Contents", "mods", "TienInspectWeapon", "42")

# Set PZ_HOME to point at the install if it is somewhere these do not guess.
PZ_CANDIDATES = [
    r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid",
    r"C:\Program Files\Steam\steamapps\common\ProjectZomboid",
    os.path.expanduser("~/.steam/steam/steamapps/common/ProjectZomboid"),
    os.path.expanduser("~/.local/share/Steam/steamapps/common/ProjectZomboid"),
    os.path.expanduser(
        "~/Library/Application Support/Steam/steamapps/common/ProjectZomboid"),
]

BG_TOP = (26, 28, 31)
BG_BOTTOM = (14, 15, 17)
GOOD = (110, 176, 92)
WORN = (206, 150, 60)
BAD = (188, 74, 58)
MUTED = (128, 136, 146)

# The canvas is drawn large and reduced at the end; every edge in it is a straight line
# or a circle, and both alias badly at 128 pixels unless they were 512 first.
SS = 4


def pz_home():
    env = os.environ.get("PZ_HOME")
    for path in ([env] if env else []) + PZ_CANDIDATES:
        if path and os.path.isdir(os.path.join(path, "media")):
            return path
    raise SystemExit(
        "Could not find Project Zomboid. Set PZ_HOME to the install directory.")


_PACK = {}


def pack_index():
    """
    Every icon in the atlas the game keeps them in, as name -> (page index, rectangle).

    media/texturepacks/UI2.pack is a run of length-prefixed entry names, each followed by
    eight little-endian int32s - x, y, w, h, offsetX, offsetY, originalW, originalH - and
    then, once per page, a plain PNG of the atlas sheet itself. The entries for a page come
    before that page's PNG, so the page an entry belongs to is the first PNG beginning
    after it.

    Built once and cached: the file is 50-odd megabytes, and re-reading it per icon turns
    dumping a couple of hundred of them into a coffee break.
    """
    if _PACK:
        return _PACK["index"]

    blob = open(os.path.join(pz_home(), "media", "texturepacks", "UI2.pack"), "rb").read()
    pages = list(zip(
        [m.start() for m in re.finditer(rb"\x89PNG\r\n\x1a\n", blob)],
        [m.start() + 12 for m in re.finditer(rb"IEND\xaeB`\x82", blob)],
    ))

    index = {}
    for match in re.finditer(rb"[A-Za-z0-9_]{3,60}", blob):
        at, run = match.start(), match.group()
        if at < 4:
            continue

        # The int32 before a name says how long it is, and that is what separates a real
        # entry from the same letters happening to appear inside PNG data. It is compared
        # against a prefix of the run rather than the whole of it, because the run does not
        # stop where the name does: the first coordinate follows immediately, and a low
        # byte like 612's 0x64 is an ASCII 'd' that the scan happily swallows.
        length = struct.unpack_from("<i", blob, at - 4)[0]
        if not 3 <= length <= len(run):
            continue

        try:
            rect = struct.unpack_from("<8i", blob, at + length)
        except struct.error:
            continue

        page = next((i for i, p in enumerate(pages) if p[0] > at), None)
        if page is not None:
            index[run[:length].decode()] = (page, rect)

    _PACK["blob"] = blob
    _PACK["pages"] = pages
    _PACK["sheets"] = {}
    _PACK["index"] = index
    return index


def pack_icon(name):
    """
    One icon, put back the size the game draws it.

    The offsets matter: the packer trims transparent margins, so pasting the cropped
    rectangle back at its offset inside an originalW by originalH canvas is what restores
    the icon's real footprint instead of leaving it flush to a corner.
    """
    index = pack_index()
    if name not in index:
        raise SystemExit("No icon named %s in UI2.pack" % name)

    page, (x, y, w, h, ox, oy, ow, oh) = index[name]
    if page not in _PACK["sheets"]:
        start, end = _PACK["pages"][page]
        _PACK["sheets"][page] = Image.open(
            io.BytesIO(_PACK["blob"][start:end])).convert("RGBA")

    icon = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
    icon.paste(_PACK["sheets"][page].crop((x, y, x + w, y + h)), (ox, oy))
    return icon


def ui_icon(name):
    """A loose UI texture, trimmed to what it actually draws."""
    path = os.path.join(pz_home(), "media", "ui", name)
    img = Image.open(path).convert("RGBA")
    return img.crop(img.split()[3].getbbox())


def paste_scaled(target, art, scale, centre):
    """
    Nearest-neighbour, and only ever by a whole number.

    These are pixel art at 32 pixels square. Smoothing them on the way up turns a crisp
    two-pixel bevel into grey mush, and a fractional scale puts some source pixels across
    two destination pixels and others across three, which reads as a wobble along every
    straight edge.
    """
    scale = max(1, int(round(scale)))
    grown = art.resize((art.width * scale, art.height * scale), Image.NEAREST)
    target.paste(grown, (int(centre[0] - grown.width / 2),
                         int(centre[1] - grown.height / 2)), grown)


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

    # A faint circle behind the weapon, the way an inspection screen frames its subject.
    r = s * 0.40
    d.ellipse([s * 0.5 - r, s * 0.5 - r, s * 0.5 + r, s * 0.5 + r], outline=(44, 48, 53),
              width=max(1, int(s * 0.006)))

    img = img.convert("RGBA")

    # The machete rather than an axe: it is the weapon whose icon reads at a glance as a
    # blade and nothing else, and it is one of the few that fills a square frame.
    weapon = pack_icon("Item_Machete")
    weapon_cx = s * (0.37 if with_bars else 0.50)
    weapon_cy = s * (0.44 if with_bars else 0.46)
    paste_scaled(img, weapon, s * (0.46 if with_bars else 0.56) * margin_scale / weapon.width,
                 (weapon_cx, weapon_cy))

    # The game's own search icon, over the blade rather than over the handle: the whole
    # subject of the mod is the state of the steel, so that is the part being looked at.
    # Small enough to read as a tool held up to the thing, not as a second subject.
    # Bigger on the icon than on the poster. The icon is read at the height of a mod list
    # row, where a lens sized for a 512 pixel poster is three pixels of teal and reads as
    # a smudge rather than as a magnifier.
    glass = ui_icon("Search_Icon_On.png")
    paste_scaled(img, glass, s * (0.20 if with_bars else 0.26) * margin_scale / glass.width,
                 (weapon_cx - s * 0.06, weapon_cy + s * 0.10))

    img = img.convert("RGB")
    d = ImageDraw.Draw(img)

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
