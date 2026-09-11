# Tien's Weapon Inspection

Press a key and your character looks the weapon in their hands over. A small window
reports what they find, and everyone on the server sees them do it.

Build 42 tracks a melee weapon's wear in three separate numbers, and the item tooltip is
not where you want to be reading them mid-fight. An axe has a handle condition and a head
condition that fall at different rates and are repaired with different materials, and
anything with an edge has a sharpness on top of both. This mod puts all of it on screen
for the weapon actually in your hands, at the cost of the second or two it takes to look.

## What it does

- **Inspect Held Weapon.** Bound to **K** by default, rebindable under *Options ->
  Key Bindings -> Weapon Inspection*. The same entry is on the right-click menu of the
  weapon you are holding.
- **It is a timed action.** Your character stops and looks, with the usual progress
  circle. Walking, running or raising the weapon cancels it. It cannot be started while
  your hands are busy with something else, or while you are driving.
- **Everyone sees it.** The inspection animation plays for every other player on the
  server, not just for you.
- **The window is the tooltip.** Deliberately. It shows what hovering the weapon shows -
  the same rows, the same labels, the same bars in the same colours, the same wording -
  and the point of the mod is that it arrives on a keypress and stays put instead of
  needing the inventory open and the mouse held still. What you read is:
  - *Condition*, labelled **Handle Condition** on a weapon that also has a head, which is
    what the game itself calls it.
  - **Head Condition**, on axes, hammers and crafted spears.
  - **Sharpness**, on anything with an edge.
  - **Damage**, on the same scale the game rates every weapon by.
  - **Handle Repaired** and **Head Repaired** counts, when it has been.
  - For firearms: **Ammo Count**, **Ammo Type**, spent rounds, and the game's own
    warnings - *Weapon jammed. Rack it.*, *No round in chamber. Rack it.*,
    *Need Magazine to operate.*

  The bars carry no numbers, because the game's do not: it never puts a figure on a
  weapon's wear anywhere you can see one. Their colour runs from your **bad** highlight
  colour to your **good** one exactly as the tooltip's do, so if you have changed that
  pair - as anyone on the colourblind-friendly setting has - the window follows.
- **It stays honest.** The window re-reads the weapon every frame, so sharpening or
  repairing it while the window is open corrects the bars as you watch. Put the weapon
  away and the window closes. Press the key again to dismiss it.

Inspecting changes nothing about the weapon. It is a look, not a service.

## Sandbox options

One setting on the **Tien's Weapon Inspection** page:

- **Inspection Time (seconds).** Seconds of real time the look takes, 2.5 by default. A
  firearm takes a quarter longer than a melee weapon, and every level of Maintenance
  takes 2.5 percent off. The game stretches any timed action further for an unhappy,
  drunk, cold or wounded character, so it is a baseline rather than a guarantee.

## Compatibility

Build 42 only. Safe to add to an existing save and safe to remove: the mod stores nothing
on any item and changes nothing about the world.

Multiplayer is supported and needs no setup beyond the mod being installed on the server
and on the clients. Nothing is sent by this mod; the animation reaches other players
through the engine's own player-state replication, which is the same path every vanilla
timed action uses. See [the implementation notes](docs/implementation.md).

Other mods' weapons work, including ones with condition fields this mod has never heard
of - every value is read behind a guard, and a weapon that answers nothing gets a window
that says so rather than a Lua error.

The mod ships almost no text of its own. Every label and every warning in the window is
the game's own translation key, so the window speaks whatever language you play in and
has nothing to keep in step with a vanilla rewording.

## Repository layout

    Contents/mods/TienInspectWeapon/42/     the mod itself, Build 42
      media/AnimSets/player/actions/        the inspection animation node
      media/lua/shared/                     stat reading, the timed action, translations
      media/lua/client/                     the window, the keybinding, the context menu
      media/sandbox-options.txt             the sandbox setting
    docs/implementation.md                  how it works against the Build 42 API
    scripts/make_art.py                     regenerates the poster, icon and preview
# Zomboid-TienInspectWeapon
