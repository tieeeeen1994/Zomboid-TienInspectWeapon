"""
The inspection clips: a raise and a looping hold for each of four weapon kinds.

    blender -b --factory-startup -P scripts/anim/clips/inspect.py -- <vanilla anims_X/Bob> <out_dir> [kind ...] [--preview]

kinds: 1H 2H Handgun Rifle (default: all). For each kind it writes
<out_dir>/Bob_TienInspect_<kind>_Raise.x and _Hold.x (+ .blend), and with --preview
renders the raise followed by one pass of the hold into <out_dir>/prev_<kind>/ for gif.py.

The brief is "calm and practical": someone checking a weapon over, not showing off.

- Raise (RAISE_FRAMES): from the kind's vanilla idle (the pose the character is in when the
  key is pressed) up into the hold's first pose. Short, because the raise lasts the sandbox
  InspectSeconds (0.5 s by default, a little longer for guns and shorter with Maintenance);
  if the action outlasts it the clip holds its last frame, if it ends sooner the hold's
  0.3 s blend covers the rest. Its last frame is the hold's first, so nothing pops.
- Hold (HOLD_FRAMES, looping, as long as the window is open): the looking. Present the
  weapon, turn it to one side and pause, to the other side and pause, then a closer check
  (along the edge / down the length / down the sights), and back.

Each kind's weapon is posed with rig.Key values; see rig.py for what they mean and for the
character-space coordinates (ch(right, up, forward), shoulder at 0.74, arm reach 0.274).
The preview weapons are vanilla models whose script has no Bip01_Prop1 attachment, so they
sit in Prop1's space exactly as in game.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import pose  # noqa: E402
import rig  # noqa: E402
import x_export  # noqa: E402
import x_import  # noqa: E402
import x_preview  # noqa: E402
import xanim  # noqa: E402
from rig import Key, ch, UP  # noqa: E402

RAISE_FRAMES = 18   # 0.6 s
HOLD_FRAMES = 240   # 8 s loop
MODELS = os.path.join(x_preview.MEDIA, "models_X")


def kind_1h():
    """Machete, knife, hammer, hatchet: blade up in front of the chest, flat to the eyes."""
    # wrist=(None, 0): the blade leans as a relaxed wrist holds it, not cocked sideways to point exactly
    A = dict(pos=ch(0.03, 0.62, 0.15), along=ch(-0.35, 0.8, 0.45), roll=0, look=0.85, lean=5, wrist=(None, 0))
    return dict(
        base="Bob_Idle", aux=None, weapon="weapons/1handed/Machete.x", poi=0.17, top=None,
        raise_keys=[Key(0, look=0, lean=0), Key(RAISE_FRAMES, ease=True, **A)],
        hold_keys=[
            Key(0, **A),
            # turn the forearm to show one face, tip leaning out a little
            Key(55, pos=ch(0.05, 0.64, 0.16), along=ch(-0.15, 0.85, 0.5), turn=50, ease=True),
            Key(80, ease=True),
            # and the other
            Key(135, pos=ch(0.02, 0.63, 0.15), along=ch(-0.45, 0.75, 0.45), turn=-50, ease=True),
            Key(155, ease=True),
            # down the edge: lower and out, tip away from the face, the forearm turned so the
            # edge faces the eyes (higher and closer, the elbow has to wing up to the head)
            Key(195, pos=ch(0.04, 0.58, 0.18), along=ch(-0.2, 0.9, 0.6), turn=70, lean=8, look=0.9, ease=True),
            Key(215, ease=True),
        ])


def kind_2h():
    """Bat, axe, sledge, spear: both hands, held across the body and turned over."""
    A = dict(pos=ch(0.13, 0.54, 0.09), along=ch(-0.6, 0.72, 0.25), roll=0, look=0.8, lean=5, support=1)
    return dict(
        base="Bob_IdleBat", aux=None, weapon="weapons/2handed/Baseballbat.x", poi=0.32, top=None,
        raise_keys=[Key(0, look=0, lean=0, support=1), Key(RAISE_FRAMES, ease=True, **A)],
        hold_keys=[
            Key(0, **A),
            # tip the head of the weapon in towards the face and turn it
            Key(60, pos=ch(0.13, 0.56, 0.1), along=ch(-0.5, 0.82, 0.12), roll=35, ease=True),
            Key(85, ease=True),
            Key(140, pos=ch(0.12, 0.55, 0.1), along=ch(-0.62, 0.7, 0.2), roll=-35, ease=True),
            Key(160, ease=True),
            # level across the chest, a look along its length
            Key(195, pos=ch(0.15, 0.62, 0.06), along=ch(-0.85, 0.35, 0.2), roll=0, lean=7, ease=True),
            Key(215, ease=True),
        ])


def kind_handgun():
    """Pistol, revolver: level in front of the chest, rolled to each side, then down the sights."""
    A = dict(pos=ch(0.05, 0.66, 0.11), along=ch(-0.4, 0.3, 0.85), top=UP, roll=0, look=0.85, lean=4, support=0, aux=0)
    return dict(
        base="Bob_IdleHandgun", aux="Bob_IdleAimHandgun", weapon="weapons/firearm/M9_Pistol.x", poi=0.07, top=-1,
        support_from_aux=True,
        raise_keys=[Key(0, look=0, lean=0), Key(RAISE_FRAMES, ease=True, **A)],
        hold_keys=[
            Key(0, **A),
            # roll it to show the right side
            Key(55, pos=ch(0.06, 0.68, 0.12), roll=-70, ease=True),
            Key(80, ease=True),
            # and the left
            Key(130, pos=ch(0.04, 0.67, 0.11), roll=70, ease=True),
            Key(150, ease=True),
            # both hands, a moment down the sights (the aim pose, a little lower)
            Key(185, at_aux=True, drop=0.03, aux=0.75, support=1, look=0, lean=0, roll=0, ease=True),
            Key(210, at_aux=True, drop=0.03, ease=True),
        ])


def kind_rifle():
    """Rifle, shotgun: both hands, across the chest, rolled to each side, then shouldered."""
    A = dict(pos=ch(0.1, 0.6, 0.06), along=ch(-0.7, 0.45, 0.55), top=UP, roll=0, look=0.8, lean=4, support=1, aux=0)
    return dict(
        base="Bob_IdleRifle", aux="Bob_IdleAimRifle", weapon="weapons/firearm/MSR788_Rifle.x", poi=0.12, top=1,
        raise_keys=[Key(0, look=0, lean=0, support=1), Key(RAISE_FRAMES, ease=True, **A)],
        hold_keys=[
            Key(0, **A),
            # tilt it to look at the right side (bolt, ejection port)
            Key(60, pos=ch(0.1, 0.62, 0.07), roll=-45, ease=True),
            Key(85, ease=True),
            # and the left
            Key(140, pos=ch(0.09, 0.61, 0.06), roll=40, ease=True),
            Key(160, ease=True),
            # shoulder it and look down the sights
            Key(190, at_aux=True, drop=0.02, aux=0.85, look=0, lean=0, roll=0, ease=True),
            Key(212, at_aux=True, drop=0.02, ease=True),
        ])


KINDS = {"1H": kind_1h, "2H": kind_2h, "Handgun": kind_handgun, "Rifle": kind_rifle}


def build(src_dir, out_dir, kind, preview=False):
    spec = KINDS[kind]()
    src = os.path.join(src_dir, spec["base"] + ".x")
    xa = xanim.read(src, with_mesh=True)
    base = pose.from_clip(xa, 0)
    aux = None
    if spec["aux"]:
        # the aim clips lack the *Nub bones of the 45-bone idles; those keep the base's values
        aux = pose.copy(base)
        found = pose.from_clip(xanim.read(os.path.join(src_dir, spec["aux"] + ".x")), 0)
        aux.update({b: m for b, m in found.items() if b in base})
    r = rig.Rig(xa, base, aux=aux, poi=spec["poi"], top=spec["top"], support_from_aux=spec.get("support_from_aux", False),
                rest=x_import.rest_matrices(xa))
    raise_poses = r.build(spec["raise_keys"], RAISE_FRAMES, breath=(0, None), from_base=True)
    hold_poses = r.build(spec["hold_keys"], HOLD_FRAMES, period=HOLD_FRAMES, breath=(0.8, HOLD_FRAMES / 2))
    if r.warnings:
        print("[inspect] %s: %d frames out of reach, worst: %s" % (kind, len(r.warnings), max(r.warnings, key=lambda w: float(w.rsplit(" ", 1)[1]))))
    if r.wrist_warnings:
        print("[inspect] %s: %d arm-frames with the wrist past its natural range, e.g. %s" % (kind, len(r.wrist_warnings), r.wrist_warnings[0]))
    for side in "RL":
        sw = [deg for s, deg in r.swivels if s == side]
        if sw:
            jump = max(abs(b - a) for a, b in zip(sw, sw[1:])) if len(sw) > 1 else 0
            print("[inspect] %s: %s elbow swing %.0f..%.0f deg, largest step %.1f" % (kind, side, min(sw), max(sw), jump))
    os.makedirs(out_dir, exist_ok=True)
    weapon = os.path.join(MODELS, spec["weapon"])
    prev_dir = os.path.join(out_dir, "prev_" + kind)
    for part, poses, offset in (("Raise", raise_poses, 0), ("Hold", hold_poses, RAISE_FRAMES + 2)):
        name = "Bob_TienInspect_%s_%s" % (kind, part)
        arm_ob = x_import.load(src)
        pose.bake(arm_ob, xa, poses, name)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name + ".blend"))
        x_export.export(src, os.path.join(out_dir, name + ".x"), name, arm_ob)
        if preview:
            frames = list(range(0, len(poses), 2))
            x_preview.render(prev_dir, frames, weapon, offset=offset, arm_ob=arm_ob)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]
    kinds = args[2:] or list(KINDS)
    for k in kinds:
        build(args[0], args[1], k, preview)
