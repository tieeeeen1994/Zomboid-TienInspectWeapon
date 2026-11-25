# Tien's Weapon Inspection

Hit a key and your character holds up whatever weapon they're carrying and gives it a
proper look. A little window tells you how it's holding up.

No more digging through your inventory and hovering the mouse just to find out if your axe
is about to snap.

## What you get

- Press **K** to inspect. Rebind it in the options if you like, or use the right-click menu.
- You'll see condition, sharpness, damage, and how many times it's been repaired. Guns show
  ammo, whether they're jammed or empty, and how much battery a fitted weapon light or laser
  has left.
- Using Gunworks Gang guns? You'll also see which round is in the chamber and what's
  loaded in the magazine, so a mixed load of ball and armour-piercing is easy to check.
  Taped jungle magazines show the side in the gun out of its 30 and the rounds waiting on
  the other side, and suppressors that wear out show their condition.
  Guns also show their fire mode (and rate of fire where it can be set), whether the bolt is
  locked open, whether a folding stock, bipod or bayonet is folded or out, and what is loaded
  in an underbarrel launcher (or in the rifle, while the launcher is in use). Parts that
  swap between two states (folding foregrips, rail bipods) show which one is fitted.
- A fitted weapon light shows whether it is switched on. With Guns of Tien, so does a
  fitted laser, and a gun with its
  bayonet in use shows the ammo still loaded in it.
- Guns show their optimal range: the distances where your shots are most likely to hit,
  for your Aiming skill and whatever sight is fitted.
- Axes and hammers show the handle and the head separately, because they wear out at
  different rates.
- You can walk around while inspecting. Running or raising your weapon cancels the inspection.
- Drag the window wherever you like and it opens there next time. The gear in its corner
  picks which point of the window stays put as it grows and shrinks, and resets it back
  above the hotbar.
- Too much on screen? **Manage Information** in the gear menu opens a list of checkboxes:
  untick what you don't need (damage, range, fire mode, batteries...) and the window gets
  shorter. Remembered for next time. **Reset Information** in the same menu shows everything
  again, without touching where the window sits.
- You'll need some light. Too dark to read is too dark to inspect.
- Other players see the animation, so it works in multiplayer.
- Three ways to inspect, picked with **Inspect Mode** in the sandbox settings:
  - **Default**: your character raises the weapon and holds it up while you read. Doing
    anything else puts it away.
  - **Persistent** (beta): your character studies the weapon for a moment, then the window
    opens and stays open through fights, runs and whatever else you get up to, until you
    close it, press the key again, or put the weapon away.
  - **Easy** (beta): no animation, no waiting. The window pops up the moment you press the
    key, always shows whatever is in your hands, and stays until you close it or press the
    key again.

## Settings

Inspect Mode (Default, Persistent (beta) or Easy (beta), Default unless changed), how
long the inspection takes, and how long your character keeps holding the weapon up. The
sandbox page explains each mode right under the mode setting.

## Information

Build 42 only. Safe to add or remove from an existing save. Works with modded weapons, and
in whatever language you play in.

## For anyone poking at the code

    Contents/mods/TienInspectWeapon/42/     the mod itself, Build 42
      media/AnimSets/player/actions/        the animation nodes (raise, and hold per weapon kind)
      media/anims_X/Bob/                    the mod's own hold clips
      media/lua/shared/                     stat reading, the three timed actions, translations
      media/lua/client/                     the window, the keybinding, the context menu
      media/sandbox-options.txt             the sandbox settings
    docs/implementation.md                  how it works against the Build 42 API
    docs/vanilla-animations.txt             every clip m_AnimName can name, for reference
    docs/icons/                             vanilla weapon icons, raw material for art
    scripts/make_art.py                     regenerates the poster, icon and preview
    scripts/anim/                           builds the animation clips in Blender
    scripts/dump_icons.py                   refills docs/icons from the game install

The raise is vanilla's looting animation. The look that follows is the mod's own: a
looping clip for one-handed weapons, two-handed weapons, handguns and long guns, generated
in Blender by `scripts/anim/`.
[docs/implementation.md](docs/implementation.md) has the detail.
