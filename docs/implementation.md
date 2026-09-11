# Tien's Weapon Inspection, implementation notes

How the mod works against the Build 42 API. The player-facing description lives in the
[readme](../README.md).

Every claim about the engine below was read out of the Build 42 install rather than
assumed: `media/lua` and `media/AnimSets` for the Lua and animation side, and the
constant pools and bytecode of `projectzomboid.jar` for the Java getters, which are what
the Lua API actually is.

## The three condition numbers

Build 42 splits a melee weapon's wear across three independent values on `InventoryItem`:

| What | Getter | Guard | Script property |
| --- | --- | --- | --- |
| Haft or handle | `getCondition()` / `getConditionMax()` | always present | `ConditionMax` |
| Head | `getHeadCondition()` / `getHeadConditionMax()` | `hasHeadCondition()` | `HeadCondition` |
| Edge | `getSharpness()` / `getMaxSharpness()` | `hasSharpness()` | `Sharpness` |

The vanilla `Axe` sets all three:

```
ConditionMax = 13,
HeadCondition = 13,
HeadConditionLowerChanceMultiplier = 1.5,
Sharpness = 1.0,
```

The guards are not politeness. Most weapons have no head, and `getHeadCondition()`
returns a meaningless number for them rather than failing, so a mod that reads it
unguarded invents a statistic.

`getCondition()` is named for what it is only when there is a head to distinguish it
from: the game's own tooltip prints `Tooltip_weapon_HandleCondition` when the item has a
head condition and `Tooltip_weapon_Condition` when it does not, and this mod does the
same so it never teaches the player a name the rest of the game contradicts.

### The repair counters, which are a trap

`getHaveBeenRepaired()` and `getTimesRepaired()` are the same field. The bytecode is
identical:

```
getHaveBeenRepaired()I     getTimesRepaired()I
  aload_0                    aload_0
  getfield haveBeenRepaired  getfield haveBeenRepaired
  ireturn                    ireturn
```

That field has no initialiser, so it starts at Java's default of `0`, and
`FixingManager.fixItem` advances it with `setHaveBeenRepaired(getHaveBeenRepaired() + 1)`.
The number it holds is therefore the number of repairs, with nothing to subtract - which
is worth stating because the Build 41 convention it replaced counted from one.

`getTimesHeadRepaired()` is the real trap. It reads an item attribute, and *falls back to
`haveBeenRepaired`* when the attribute is absent:

```
getTimesHeadRepaired()I
  ... attrib().contains(TIMES_HEAD_REPAIRED) ...
  ifeq  ->  aload_0; getfield haveBeenRepaired; ireturn
```

So on any weapon without a head, asking for head repairs returns the handle's count.
`hasTimesHeadRepaired()` is the gate that stops the window printing the same number twice
under two labels, and this mod checks it before reading.

## The window is a copy of the tooltip, on purpose

The mod's worth is the delivery, not the presentation: hovering an item to read its
condition needs the inventory open and the mouse held still, and a window that appears on
a keypress and stays put is better at exactly that. So the window shows what the tooltip
shows, and every departure from it had to justify itself and mostly could not.

The tooltip is built in two Java methods, and between them they are the whole
specification this window is written against:

**`InventoryItem.DoTooltipEmbedded`**, which every item gets:

```
setLabel Tooltip_weapon_AmmoCount       setValue     getCurrentAmmoCount() "/" getMaxAmmo()
setLabel Tooltip_handle_Repaired        setValue     the repair count
setLabel Tooltip_head_Repaired          setValue     the head repair count
setLabel Tooltip_weapon_Sharpness       setProgress  getSharpness()
setLabel Tooltip_weapon_HandleCondition setProgress  getCondition() / getConditionMax()
```

**`HandWeapon.DoTooltip`**, which weapons add:

```
setLabel Tooltip_weapon_Sharpness       setProgress  getSharpness()
setLabel Tooltip_weapon_HandleCondition setProgress  getCondition() / getConditionMax()
setLabel Tooltip_weapon_HeadCondition   setProgress  getHeadCondition() / getHeadConditionMax()
setLabel Tooltip_weapon_Damage          setProgress  (getMaxDamage() + getMinDamage()) / 5
setLabel Tooltip_weapon_Jammed                       (no value - the label is the sentence)
setLabel Tooltip_weapon_NoRoundChambered             (no value)
setLabel Tooltip_weapon_SpentRoundChambered          (no value)
setLabel Tooltip_weapon_SpentRounds     setValue     getSpentRoundCount()
setLabel Tooltip_weapon_ContainsClip                 (no value)
setLabel Tooltip_weapon_NoClip                       (no value)
```

Four things follow from that, and the code does all four:

**No numbers on the bars.** Wear reaches the tooltip as `setLabel` then
`setProgress(fraction, r, g, b, alpha)` with no `setValue` beside it, which means the game
never puts a figure on a weapon's condition anywhere the player can see one. The raw
`11 / 13` is not a number they have ever been shown, so printing it here would be this mod
inventing a statistic. `bar()` carries a ratio and nothing else.

**Counts are text, not bars.** The game keeps the distinction and so does this: rounds and
repairs go through `setValue` because they are quantities, and only the things that
degrade get a bar. It is also the only presentation that still says anything once the bars
stopped carrying numbers - an ammo *bar* with no figure on it tells you nothing about how
full a magazine is.

**The colours are the player's.** Every `setProgress` interpolates from
`Core.getBadHighlitedColor()` to `Core.getGoodHighlitedColor()` across the fraction, so
`IW.colorFor` reads those two out of `getCore()` and lerps between them rather than
hard-coding red and green. Anyone who has switched to the colourblind-friendly pair gets
their pair here as well.

**The words are the game's.** Every label and every warning uses vanilla's own translation
key - `Tooltip_weapon_AmmoCount`, `Tooltip_weapon_Jammed`, `Tooltip_handle_Repaired` and
the rest - so the wording a player already knows from the tooltip is the wording they get
here, in whatever language they play in, and the mod ships no translation of its own to
fall out of step with a vanilla rewording. Its own `IG_UI.json` is down to a window title,
three refusal messages and one fallback line.

Two small departures, both deliberate:

- Sharpness is divided by `getMaxSharpness()`, where vanilla feeds `getSharpness()` to
  `setProgress` unchanged. Vanilla is treating it as already being a fraction, which it is
  for every item in the game because the scripts set `Sharpness = 1.0` for a new edge, so
  this is the identical bar for all of them and a correct one for a modded weapon that
  chose a different scale.
- The damage divisor of 5 is a constant read out of the bytecode, not a guess. There is no
  per-weapon maximum to measure damage against, so the game scales every weapon on one
  fixed ruler; copying the ruler is what makes a half-full damage bar here mean what the
  player already learned it means.

## The animation, and why multiplayer needs no networking

This is the part worth understanding, because the obvious implementation - send a command
to the server, have it broadcast, have every client start the animation - is both
unnecessary and wrong here.

`media/AnimSets/player/actions/TienInspectWeapon.xml` adds a node to the player's
animation tree:

```xml
<m_Name>TienInspectWeapon</m_Name>
<m_AnimName>Bob_IdleLooting_Mid</m_AnimName>
<m_Conditions>
    <m_Name>PerformingAction</m_Name>
    <m_Value>TienInspectWeapon</m_Value>
</m_Conditions>
```

`AnimationSet` builds that tree by walking every `media/AnimSets/player` directory
`ZomboidFileSystem.resolveAllDirectories` can find, mods included, so a node dropped into
a mod's folder is a first-class node next to the vanilla ones. `Bob_IdleLooting_Mid` is
the clip vanilla already uses for `EquipItem`, `MedicalCheck` and `Loot`: the character
holds what is in their hands up and turns it over.

The node is selected by the `PerformingAction` character variable, which is what
`ISBaseTimedAction:setActionAnim()` sets. That variable is replicated by the engine:

1. Starting the action puts the character into `PlayerActionsState`.
2. `StateManager.enterState` sees a local player entering a state that syncs, and builds
   a `StatePacket` from `PlayerActionsState.setParams` - which packs `PerformingAction`,
   `IsPerformingAnAction`, the primary and secondary hand models, and a general
   `VARIABLES` map.
3. The packet goes to the server and is relayed to the other clients.
4. On each of them `PlayerActionsState.enter` calls `setVariable("PerformingAction", ...)`
   and `NetworkCharacterAI.setPerformingAction`, the animator matches the node out of
   *their* copy of this mod's AnimSets folder, and the remote character plays it.

This is the same path every vanilla timed action's animation travels. Adding a
`sendClientCommand` alongside it would not make the animation more reliable; it would
give a second machine a second reason to start the same animation, which is how an action
ends up playing twice or fighting its own blend. So the mod sends nothing.

Two consequences worth knowing:

- The mod must be installed on every client that should *see* the animation, not only on
  the one playing it. Without the AnimSets file a client has no node named
  `TienInspectWeapon` and falls through to `default-fallback`, which is `Bob_EmoteSurrender`
  - the character would appear to put their hands up. On a server where the mod is
  required this cannot happen.
- The server needs the mod for the same reason every mod is required server-side, but it
  runs none of this: the action's only effect is a window, and `complete()` opens it
  behind `self.character:isLocalPlayer()`.

The action deliberately does **not** call `setOverrideHandModels`. The weapon is already
in the character's hands and is already the right model; overriding would swap it for
itself and cost every client a needless re-equip.

## The action

`ISTienInspectWeaponAction` is an ordinary `ISBaseTimedAction` that changes nothing:

- `isValid()` re-finds the held weapon each tick and compares item IDs rather than object
  identity, because a multiplayer client replaces item objects wholesale when the server
  sends an update. Dropping the weapon or swapping hands ends the action.
- `start()` re-fetches the item by ID under `isClient()`, the way vanilla actions do, then
  calls `setActionAnim`.
- `stopOnWalk`, `stopOnRun` and `stopOnAim` are all set: moving or raising the weapon
  means the player has stopped looking at it.
- `getDuration()` reads the sandbox option, adds a quarter for a firearm, and takes 2.5
  percent per level of Maintenance. `isTimedActionInstant()` collapses it to one tick for
  debug and for the instant-action cheat.

  The option is in seconds, which `maxTime` is not. `BaseAction.update` does
  `currentTime += GameTime.getMultiplier()` per tick and finishes at `maxTime`, and
  GameTime's own pair of conversions says what a unit is worth:

  ```
  getMultiplierFromTimeDelta(dt) = dt * 0.8 * multiplierBias * 60
  getTimeDeltaFromMultiplier(m)  = m / 0.8 / multiplierBias / 60
  ```

  `multiplierBias` is `1.0` out of GameTime's constructor and no Lua in the game touches
  it, so one real second is `dt * 0.8 * 60` = **48 units**, frame rate independent.
  `IW.TICKS_PER_SECOND` is that 48, and it is the only reason the sandbox page can ask
  for a number in seconds.

  Whatever comes out of `getDuration()` is then stretched again by
  `ISBaseTimedAction:adjustMaxTime`, for unhappiness, drink, wounded hands and body
  temperature, so the sandbox figure is a baseline for a healthy character.
- `ignoreHandsWounds` is on and `caloriesModifier` is zero. Looking at something is not
  work, and a hurt hand does not slow down looking.

Queueing is guarded with the vanilla helpers rather than by hand:
`ISTimedActionQueue.isPlayerDoingAction` for "your hands are busy", which covers both the
action queue and the engine states that bypass it, and
`ISTimedActionQueue.hasActionType` so that leaning on the hotkey cannot stack five
inspections behind each other.

## How the window keeps itself honest

`ISTienInspectWeaponWindow` is an `ISCollapsableWindow`, one per player number so that
two players sharing a machine do not fight over one window.

It holds the weapon's **ID**, not the weapon, and re-reads it every frame through
`TienInspectWeapon.inspect()`. That is what lets a weapon sharpened or repaired while the
window is open correct itself on screen, and what lets the window close itself the moment
the weapon leaves the player's hands rather than describing something they are no longer
holding.

Every height and width in it is measured from `getTextManager()` rather than written down
as a pixel count, because the UI font size is a game option and a row sized for the
smallest setting puts its label through the bar underneath it at the largest. The window
also widens itself to fit the longest label and value it is asked to draw, so a long
weapon name or a wordier translation moves the frame instead of overflowing it.

## Reading a weapon the mod has never seen

`TienInspectWeapon.inspect()` reaches every optional getter through one helper:

```lua
local function ask(item, method, ...)
    if not item or not item[method] then return nil end
    local ok, value = pcall(item[method], item, ...)
    if not ok then return nil end
    return value
end
```

`hasSharpness()` and `hasHeadCondition()` already gate the two that matter. The `pcall` is
for everything else: this mod gets handed whatever weapon a modded server has invented,
and a missing or angry method on one line should cost that line and not the window. A
weapon that answers nothing at all produces a window saying so.

`IW.inspect()` returns rows in the order the tooltip lists them and nothing else - there
is no summary, no verdict and no grading, because the tooltip has none.

## Regenerating the art

    python3 scripts/make_art.py

Writes `poster.png` and `icon.png` into the mod folder and `preview.png` at the
repository root. Everything is drawn from primitives so the images stay editable.
