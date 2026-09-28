# Tien's Weapon Inspection — working notes

General Project Zomboid engine notes (paths, decompiling, Kahlua, networking) live in
`~/Zomboid/Workshop/ZomboidFixesB42/CLAUDE.md`. Everything about animations and Blender lives here
and only here: the pipeline, the engine's animation loading and node selection, and the rig.
Game version 42.20.4; `docs/implementation.md` explains the mod's Lua and multiplayer design.

## Custom animations (Blender pipeline)

Everything is in `scripts/anim/`, each file with a docstring explaining its part:

| file | runs in | does |
|---|---|---|
| `xanim.py` | python3 or Blender | read/write PZ text `.x` clips; `python3 xanim.py <clip.x>...` validates, `python3 xanim.py compare a.x b.x` diffs two clips |
| `x_import.py` | Blender | vanilla `.x` clip -> armature `Bob` + skinned mesh `Body` + action |
| `x_export.py` | Blender | the armature's action -> `.x` clip (evaluated pose, so constraints bake) |
| `pose.py` | Blender | author poses in code: `from_clip`, `rotate(bone, axis, deg)`, `hold_prop`, `bake` |
| `rig.py` | Blender | **weapon-first posing**: keys place the weapon (`Key(frame, pos, along, face/top, roll, turn, wrist, look, lean, aux, support, ...)`), then torso blend, lean, head look-at, two-bone IK of both arms onto the weapon with the elbow swung for a natural wrist, Prop1 back on the hand |
| `x_preview.py` | Blender | Workbench renders (front 3/4 + right side) with the vanilla machete on Bip01_Prop1 |
| `sheet.py` | python3 + Pillow | contact sheet of the renders, to look at one image |
| `gif.py` | python3 + Pillow | looping GIF of the renders at real speed, for the user (`open` it) |
| `clips/inspect.py` | Blender | **the shipped clips**: raise + hold for kinds `1H 2H Handgun Rifle`; `--preview` renders them |
| `clips/test_hold.py` | Blender | the first pipeline test clip (no longer shipped) |

Blender 5.2.2 LTS is at `/Applications/Blender.app/Contents/MacOS/Blender`; everything runs headless with
`-b --factory-startup`. Work files go in `tmp/anim/` (gitignored); only the finished `.x` is shipped.
On the Windows machine: `BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"`,
`BOB="C:/Program Files (x86)/Steam/steamapps/common/ProjectZomboid/media/anims_X/Bob"` (x_preview.py picks the game's
media folder per OS, `PZ_MEDIA` overrides it), `python` not `python3`, and pass the output folder **absolute**
(`"$(pwd -W)/tmp/anim/insp"`): Blender renders a relative one under `C:\tmp`. The user views GIFs in ImageGlass
(`C:\Program Files\ImageGlass\ImageGlass.exe <gif>`).

### Workflow

```sh
BL=/Applications/Blender.app/Contents/MacOS/Blender
BOB="$HOME/Library/Application Support/Steam/steamapps/common/ProjectZomboid/Project Zomboid.app/Contents/Java/media/anims_X/Bob"
# 1. build the inspect clips (all kinds, or name some) + previews -> tmp/anim/insp/  (~20 s a kind with --preview)
"$BL" -b --factory-startup -P scripts/anim/clips/inspect.py -- "$BOB" tmp/anim/insp [1H 2H Handgun Rifle] --preview
#    it prints "[inspect] <kind>: N frames out of reach" when a hand cannot get to the weapon: move that key closer,
#    "N arm-frames with the wrist past its natural range" (before the right wrist's soft limit), and each elbow's
#    swing range and largest frame-to-frame step (a jump of tens of degrees = the solver flipping sides: re-key)
# 2. look at it: raise frames 0-18, then the hold from 20 (hold frame f = 20 + f), every 2nd frame rendered
python3 scripts/anim/sheet.py tmp/anim/insp/prev_2H tmp/anim/insp/sheet_2H.png 0,10,18,80,100,160,200,230,250  # Read it
python3 scripts/anim/gif.py tmp/anim/insp/prev_2H tmp/anim/insp/Inspect_2H.gif 2 0.7 && open tmp/anim/insp/Inspect_2H.gif
# 3. check it
python3 scripts/anim/xanim.py tmp/anim/insp/*.x                     # each must say OK
# 4. ship it
cp tmp/anim/insp/Bob_TienInspect_*.x Contents/mods/TienInspectWeapon/42/media/anims_X/Bob/
```
A single clip of your own: `clips/test_hold.py` is the smallest example (a vanilla pose + `pose.rotate`), and any
build script ends in `pose.bake` + `x_export.export`; `x_preview.py <blend> -- <dir> every:15 [weapon.x]` renders one.

Hand-editing instead of (or after) a build script: open the `.blend` in Blender, edit the action,
save, then `"$BL" -b <file>.blend -P scripts/anim/x_export.py -- <vanilla template.x> <out.x> <Clip>`.
To start from any vanilla clip: `"$BL" -b --factory-startup -P scripts/anim/x_import.py -- "$BOB/<clip>.x" tmp/anim/<name>.blend`.
Iterate on renders first, the game last: a round in game costs a restart (or `-debug` + anim reload).

### How the game loads animation files (decompiled, 42.20)

- `FileTask_LoadAnimation` loads `.x`, `.fbx` and `.glb` through Assimp (`MAKE_LEFT_HANDED`). **Only FBX/glTF
  get `animBonesScaleModifier = 0.01` and a -90° X `animBonesRotateModifier`** (applied in
  `ImportedSkeleton.processAnimation`); `.x` is used exactly as written. Hence this pipeline writes `.x`.
- `ProcessedAiScene.processAiScene` builds clips only from a scene with a **mesh that has bones**; without one it logs
  `No such mesh` and the file gives nothing. Vanilla clips all carry the whole Bob body mesh, so `write_clip` copies
  a vanilla file's head (templates, material, frames, skinned mesh) and replaces only the AnimationSet.
- The skeleton is found by the `Dummy01` node; bone indices come from the MaleBody mesh (`skinnedTo`), and channels are
  matched by bone name. `Translation_Data` is a separate root frame (root motion).
- **Clip name = the AnimationSet's name** (text after a `|` if any, trimmed), not the file name. Keep both the same.
- Mods: `ModelManager.loadModAnimations` loads `<mod>/<version or common>/media/anims_X/<animationDirectory>/`
  (Human: `Bob`, `Kate`, `Zombie`, from `scripts/generated/animations_meshes.txt`) and, for the Human mesh, any other
  file or folder in `anims_X`. A mod clip with a vanilla clip's name replaces it (mod priority = load order).

### The rig (what the vanilla files say)

- `.x` conventions: `FrameTransformMatrix` is row-major with translation in the last row (row vectors);
  AnimationKey 0 = R as `w,x,y,z` **conjugated** (the rotation is `(w,-x,-y,-z)`), 1 = S, 2 = T;
  `AnimTicksPerSecond` 4800, a key every 160 ticks = 30 fps. Verified: each bone's first key equals its frame matrix
  to 2e-6 (`check_conventions`).
- Space: Y up, the character faces **-Z**, about 0.98 units tall (pelvis 0.505, head 0.825). It is **left-handed**:
  `Bip01_R_Hand` is at -X. In Blender the armature object gets the Y<->Z swap (determinant -1), which stands the
  character up facing -Y and un-mirrors it; armature space stays the file's space, so it never reaches the game.
- Biped bones point down their local **X** (so X = twist, Y/Z = bend in `pose.rotate`). Blender bones point down Y,
  so each Blender bone is the file bone times `C` (x_import.py), taken off again on export.
- The frames in a clip file hold **that clip's first frame**, not a common rest pose. The mesh's bind pose (arms out)
  is the inverse of each `SkinWeights` offset matrix; that is the Blender rest pose.
- **`Bip01_Prop1` (right-hand weapon) and `Bip01_Prop2` (left hand) are children of `Bip01`, not of the hands.** A
  clip that moves a hand must move the prop with it (`pose.hold_prop`, or a Child Of constraint that export bakes).
- A right-hand weapon model is drawn in Bip01_Prop1's space, offset by its model script's `attachment Bip01_Prop1`
  if it has one (`scripts/generated/models_weapons.txt`; `Machete` has none, so its `.x` vertices are Prop1-space).
- Bone sets differ per clip: `Bob_IdleLookAtPhoto` has 35 tracks, `Bob_Idle` / `Bob_IdleLooting_Mid` 45 (with the
  `*Nub` bones). Export writes a track for every bone of the template file, so pick a 45-bone template.
- Vanilla clips worth basing on: `Bob_IdleLooting_Mid` (81 frames, weapon up in front of the chest, turned over),
  `Bob_IdleLookAtPhoto` (static 2-key pose: **left** hand raised, right hand and weapon down at the hip).

### Posing notes (rig.py, clips/inspect.py)

- Character space `ch(right, up, forward)` = file `(-right, up, -forward)`. Shoulder joint at up 0.74, right 0.095,
  forward -0.03; upper arm and forearm are 0.137 each, so a wrist reaches **0.274** from the shoulder. Keep hand targets
  under ~90% of that; rig.py records every frame a hand falls short.
- Weapon models (`media/models_X/weapons/...`): long axis local **+Y** from the grip; flat side / side of a gun faces
  local **X**; a rifle's top (scope) is **+Z**, a handgun's (M9, revolver) is **-Z**. Models with no
  `attachment Bip01_Prop1` in `models_weapons.txt` (390 of 400: machete, bat, M9 `Handgun03`, `HuntingRifle`, ...) sit
  in Prop1 space as they are. Preview models: `1handed/Machete`, `2handed/Baseballbat`, `firearm/M9_Pistol`,
  `firearm/MSR788_Rifle`.
- Grip offsets come from the base idle: right hand to Prop1 (`grip_r`), Prop1 to left hand (`support`). Idles per kind
  (from `AnimSets/player/idle`): `Bob_Idle` (1handed, knife, unarmed), `Bob_IdleBat` (2handed, spear),
  `Bob_Idle2H_Heavy` (heavy), `Bob_IdleHandgun`, `Bob_IdleRifle` (firearm), `Bob_IdleChainsaw`. The idles are static
  2-key poses; `Bob_IdleBat` has 35 bones, the others 45.
- The aim poses (`Bob_IdleAimHandgun`, `Bob_IdleAimRifle`, 35 bones) turn the **pelvis 31°** (bladed stance) and
  Spine1 ~50-60°. Blending the legs would slide the feet, so rig.py re-roots `Bip01_Spine` to keep the aim torso's
  world orientation on the idle hips, and fills the aim pose's missing bones from the base.
- A handgun idle's left hand hangs at the side, so its left-hand grip comes from the aim pose (`support_from_aux`).
- Two-bone IK keeps Biped's hinge: the elbow bends about the upper arm's local axis the base pose bends it about, the
  upper arm is set from two vector pairs (to elbow, forearm direction), the elbow starts along the base elbow's
  direction in Spine1's frame (+ key `elbow`).
- **Human wrists** (measured over all 1614 vanilla Bob clips, relative to the bind pose): the forearm bone **never
  twists** (only its Y hinge moves); the hand bone carries all pronation/supination (twist 1st-99th percentile about
  ±85°), and its bends stay within about -20..70° (Y) and -40..65° (Z), median (16°, 5°) right hand. So rig.py keeps
  the forearm a pure hinge (twisting it wrings the elbow skin), swings the elbow about the shoulder-wrist line each
  frame to the angle that keeps the wrist nearest natural (cost: wrist bends / 50°, 45°, twist / 80°, swing / 60°, a
  lifted elbow), and soft-limits the right wrist (the weapon gives way; the left hand grips where it really ended up),
  fading the limit out towards the vanilla aim pose, which is trusted as is.
- A **roll about a blade held in a hammer grip** (blade square to the forearm) can only come from bending the wrist
  60-90°: show a blade's faces with key `turn` (the forearm's rotation) instead, and `wrist=(None, 0)` to let the blade
  lean as a relaxed wrist holds it. A handgun's barrel runs along the forearm, so its `roll` already is a forearm turn.
  Keys that ask for an orientation reachable only with a lifted elbow get a chicken wing: move the grip lower/out.
- The raise's last frame is the hold's first (checked: seam 0.00000; the elbow swing has no frame-to-frame memory for
  this reason) and the hold's wrap step is smaller than a normal frame step. Its first frame is **not** quite the idle:
  the IK rebuild turns the right upper arm 24° (1H, Handgun), 10° (2H), 7° (Rifle) off it; the node's blend-in hides it.

### Picking a clip per weapon (decompiled, 42.20)

- The animation variable **`Weapon`** is set on every machine from `WeaponType.getWeaponType(chr).getType()` whenever
  a hand item changes (`IsoGameCharacter` set primary/secondary; `IsoPlayer` keeps it in `weaponT`): `""` unarmed,
  `1handed`, `2handed` (both hands on a two-handed weapon), `heavy` (SwingAnim Heavy), `knife` (Stab), `spear`,
  `handgun`, `firearm` (two-handed gun), `throwing`, `chainsaw`. A two-handed weapon in one hand is `1handed`.
- `AnimState.addNode` sorts nodes by `compareSelectionConditions` (abstract last, then `m_ConditionPriority`, then
  **number of conditions**); `getAnimNodes` returns the first matching node and any equally specific ones. So a node
  with `PerformingAction` + `Weapon` beats the same `PerformingAction` alone.
- Leaving a node (its conditions stop matching) fades it out over `LiveAnimNode.getBlendOutTime`: a transition's
  time if one matches, else `m_BlendOutTime`, else the node's own `m_BlendTime` (`AnimNode.getBlendOutTime`), while
  the next node fades in over `getBlendInTime` (the transition's `m_blendInTime`, else its own `m_BlendTime`); weights
  eased with `PZMath.lerpFunc_EaseOutInQuad`. **Weights are not normalised**
  (`AnimationPlayer.updateBoneAnimationTransform`, tracks ordered by `LiveAnimationTrackEntries.setTracks`: priority,
  then weight): the heavier track takes its weight first, the next only fills what is left, the previous frame's bone
  fills any rest. So the incoming node's blend-in decides the fade: an idle's 0.2 s takes over at ~0.13 s whatever the
  outgoing `m_BlendOutTime` (0.5 there only snaps harder). The way to slow it is an `m_Transitions` entry
  (`m_Target` = the next node's `m_Name`, `m_blendInTime`, `m_blendOutTime`, optional `m_AnimName` clip played in
  between), found by `AdvancedAnimator.FindTransitionsFromProxy` across states too (vanilla `RackRifleAim` ->
  `IdleRifle`). The hold nodes list all 19 idle nodes at 0.5/0.5. Per-bone blend: hands do not stay on a two-handed
  weapon during it.
- Conditions are ANDed; an `<m_Type>OR</m_Type>` entry starts a new group (`AnimCondition.pass`). Types: STRING,
  STRNEQ, BOOL, EQU, NEQ, LESS, GTR, ABSLESS, ABSGTR, OR.

### Pitfalls met

- The text `AnimTicksPerSecond` first appears in the header's `template` block; cut a template file at the line that
  *starts* with it (`^AnimTicksPerSecond`), or the frames and mesh are lost and the game rejects the clip.
- Keep quaternions in one hemisphere from key to key (`make_compatible` on import, sign flip on export), or Blender's
  per-channel interpolation spins bones between keys.
- `write_clip` drops keys inside runs of identical values (vanilla does the same); a full key per frame per bone
  roughly triples the file.

### Current state

The shipped clips are `Bob_TienInspect_{1H,2H,Handgun,Rifle}_{Raise,Hold}` (built by `clips/inspect.py`, installed in
`42/media/anims_X/Bob/`). `TienInspectWeapon.xml` / `TienInspectWeaponHold.xml` play the 1H pair and are the fallback;
`TienInspectWeapon{,Hold}_{2H,Handgun,Rifle}.xml` add the `Weapon` condition. The pipeline was proven in game with
the test clip (2026-09-28); the eight clips are built and previewed, **not yet tried in game** (standing and walking).
