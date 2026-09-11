#!/usr/bin/env python3
"""
Pull vanilla item icons out of the game and drop them in docs/icons, as raw material for
anyone drawing art for this mod.

    python3 scripts/dump_icons.py              # weapons, which is what this mod is about
    python3 scripts/dump_icons.py Axe Machete  # anything whose name contains one of these
    python3 scripts/dump_icons.py --all        # all ~2900 of them

Icons come out at the size the game stores them, usually 32x32, transparent background.
They are pixel art: scale them by whole numbers with nearest-neighbour, or they turn to
mush. See paste_scaled in make_art.py.

The extraction itself lives in make_art.py, which needs it anyway to build the poster.
This script is only a filter and a loop over it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_art

OUT = os.path.join(make_art.ROOT, "docs", "icons")

# What a weapon icon is called, near enough. The pack has no category field, so matching on
# the name is the only handle there is - which is why the filter is a list of substrings
# rather than anything cleverer.
WEAPON_WORDS = [
    "Axe", "Machete", "Knife", "Dagger", "Sword", "Katana", "Spear", "Hammer", "Sledge",
    "Crowbar", "Bat", "Club", "Cleaver", "Saw", "Shovel", "Pickaxe", "Wrench", "Pistol",
    "Revolver", "Rifle", "Shotgun", "Chainsaw",
]


def main():
    args = [a for a in sys.argv[1:] if a != "--all"]
    everything = "--all" in sys.argv[1:]
    words = args or WEAPON_WORDS

    index = make_art.pack_index()
    names = sorted(n for n in index if n.startswith("Item_"))
    if not everything:
        names = [n for n in names if any(w.lower() in n.lower() for w in words)]

    if not names:
        raise SystemExit("Nothing matched %s" % ", ".join(words))

    os.makedirs(OUT, exist_ok=True)
    for name in names:
        make_art.pack_icon(name).save(os.path.join(OUT, name + ".png"))

    # The loose UI textures the current art uses, which are not in the pack at all. Worth
    # having beside the weapons: the magnifier is the half of the icon that says the mod is
    # about looking at the thing rather than swinging it.
    for name in ("Search_Icon_On.png", "Search_Icon_Off.png"):
        make_art.ui_icon(name).save(os.path.join(OUT, name))

    print("wrote %d icons to %s" % (len(names) + 2, OUT))


if __name__ == "__main__":
    main()
