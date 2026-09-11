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
one refusal message and one fallback line.

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

`TienInspectWeaponHold.xml` is the second node, for the second half. It takes
`Bob_IdleLookAtPhoto`, a character holding something up in front of them and studying it.
None of the looting clips manage that gesture - they are rummaging motions, hands passing
over things rather than settling on one - and the difference shows once the pose is held
rather than glimpsed.

That it is a genuine `Idle*` clip matters as much as the pose. The hold can run for the
whole sandbox ceiling, so it has to survive looping, and an idle is authored to loop where
an action clip is authored to finish.

It sets `m_Looped` true, which nothing in vanilla's `actions` folder does, because every
vanilla action is short enough to finish. This one is not: it can run for the whole sandbox
ceiling. The precedent for a node that has to keep going is `idle.xml`, `walk.xml` and
`run.xml`, which are the only player nodes in the game that set it.

### Why both clips are vanilla

Every animation here is one the game already ships. A purpose-made inspect clip is
tempting - a pistol is held differently from an axe, and one pose covering both is a
compromise - but a clip authored to be played standing still is not automatically a clip
that survives a walk, and this mod lets the player walk.

Worth recording for anyone who revisits this: `media/anims_X/` takes `.fbx`, not only the
`.X` files the folder name implies, so authoring a clip does not mean hunting down a
DirectX exporter. And leg keys are not the obstacle they look like - `Bob_IdleLooting_Mid`
animates 42 bones including the pelvis, thighs, calves and feet, and `ISEquipWeaponAction`
plays it with `stopOnWalk` false regardless, so the engine is blending over locomotion
rather than deferring to the clip.

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

## The two actions

An inspection is two chained `ISBaseTimedAction`s, neither of which changes anything:

`ISTienInspectWeaponAction` is the **wind-up**. An ordinary countdown with a progress
circle, playing the `TienInspectWeapon` node, no window. Its `complete()` queues the hold
and returns.

`ISTienInspectWeaponHoldAction` is the **hold**. It plays the `TienInspectWeaponHold` node,
opens the window as it starts, and keeps the character in the pose for as long as the
player is reading.

The split is what puts a beat between the keypress and the window, and it is what lets each
half have its own clip - the wind-up is a motion with a duration, the hold is a pose being
held, and one clip stretched across both reads as a loop nobody chose.

The hand-off is the ordinary chained-action one. `ISTimedActionQueue.add` called from inside
`complete()` finds `isCurrentActionAddingOtherActions()` false and appends normally; because
the wind-up is still in the queue at that moment, `addToQueue` sees a non-zero count and does
not begin the hold early. `perform()` then reaches `onCompleted`, which pops the wind-up and
begins the hold.

Project Zomboid has no action that runs until cancelled. Nothing in the game's Lua sets an
unbounded `maxTime` and only three files touch `isUsingTimeout`, so the hold is a long
countdown with the sandbox ceiling as its length rather than an open-ended state.

- `isValid()`, on both, re-finds the held weapon each tick and compares item IDs rather than
  object identity, because a multiplayer client replaces item objects wholesale when the
  server sends an update. Dropping the weapon or swapping hands ends the action.
- `start()`, on both, re-fetches the item by ID under `isClient()`, the way vanilla actions
  do, then calls `setActionAnim`. The hold's also opens the window.
- `useProgressBar` is false on the hold and left alone on the wind-up. The circle counts
  down a deadline, which is what the wind-up is and what the hold's ceiling is not.
- `stopOnRun` and `stopOnAim` are set on both; `stopOnWalk` is deliberately false. The
  engine blends an action anim over locomotion without help, and `ISEquipWeaponAction` plays
  the wind-up's very clip while walking, so a character can look a weapon over on the move.
  Breaking into a run or raising the weapon still ends it.
- The wind-up's `getDuration()` reads `InspectSeconds`, adds a quarter for a firearm, and
  takes 2.5 percent per level of Maintenance. That scaling belongs here rather than on the
  hold, because this is the half that is actually the character doing something; how long
  the window then stays up is the player's question, not theirs.
- The hold's `getDuration()` reads `MaxHoldSeconds` and scales it by nothing.
  `isTimedActionInstant()` is ignored there for the same reason `adjustMaxTime` is
  overridden to the identity: a hold collapsed to one tick by the instant-action cheat would
  open the window and shut it in the same frame, and stretching a ceiling because the
  character is cold would make the sandbox number meaningless.

  The hold gets a new key rather than borrowing `InspectSeconds`, and the wind-up keeps
  that old key. Sandbox values are stored per save, so a key's meaning has to stay put: a
  save that chose `InspectSeconds = 2.5` chose how long the character spends looking the
  weapon over, which is exactly what the wind-up is, and that number lands where it was
  meant to. Pointed at the hold's ceiling instead - as it briefly was - the same 2.5 becomes
  a window that shuts before it can be read.

  Both options are in seconds, which `maxTime` is not. `BaseAction.update` does
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

- `ignoreHandsWounds` is on and `caloriesModifier` is zero. Looking at something is not
  work, and a hurt hand does not slow down looking.

### Ending the hold

Window and action share one lifetime in both directions. `start()` hands the window a
back-reference to the action; the window's `close()` calls `forceStop()` through it, and
the action's own exits clear that reference before closing the window. Clearing it first is
the whole of the re-entrancy guard - the window only reaches back for a `forceStop` while it
still believes an action is running.

Walking is not one of the endings. `stopOnWalk` is false and plain movement never enters
the action queue, so a character can read and walk at the same time.

Anything the player asks for next ends it, and `update()` does that with `forceComplete()`
rather than by failing `isValid()`. The difference matters: `ISBaseTimedAction:stop` calls
`resetQueue`, which wipes the whole queue and would cancel the very action just queued
behind the hold, where completing pops the hold off and lets `onCompleted` begin the next
one. Vanilla's `WalkToTimedAction` ends itself from `update` the same way.

A press while the character is already busy appends rather than interrupts:
`ISTimedActionQueue.add` never splices in front, so reloading or barricading finishes and
the look happens after. The one queueing guard is `ISTimedActionQueue.hasActionType`, so
that leaning on the hotkey cannot stack five inspections behind each other.

## Light

The requirement is `IsoGameCharacter:tooDarkToRead()`, and the refusal is vanilla's
`ContextMenu_TooDarkToInspect` - the pairing vanilla itself uses to gate the Inspect
option on print media, in `ISInventoryPaneContextMenu.doPrintMediaMenu`. Taking the
engine's own predicate rather than reading `getLightLevel()` off the square means an
equipped torch, a headlamp and the room's lights all count without this mod deciding what
a light source is, and means the threshold moves with vanilla if vanilla moves it.

It is checked twice. `IW.canInspect` refuses the keypress, and the action's `isValid()`
checks again every tick, the way `ISReadABook` does - the action can wait in the queue
behind something else, and a torch can burn out mid-look.

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
