"""
Bob_TienInspect_Test: the pipeline test clip. Not a finished animation.

Bob_IdleLooting_Mid's first frame (weapon up in front of the chest in the right hand),
held, with the right forearm rolling the blade over and back and the wrist tilting with
it, in a 3 second loop (frame 90 = frame 0). The weapon is kept in the hand by
pose.hold_prop, since Bip01_Prop1 is a child of Bip01, not of the hand.

    blender -b --factory-startup -P scripts/anim/clips/test_hold.py -- <vanilla anims_X/Bob> <out_dir>

Writes <out_dir>/Bob_TienInspect_Test.blend and .x.
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pose  # noqa: E402
import x_export  # noqa: E402
import x_import  # noqa: E402
import xanim  # noqa: E402

NAME = "Bob_TienInspect_Test"
SOURCE = "Bob_IdleLooting_Mid.x"
FRAMES = 90  # 3 s at 30 fps


def build(src_dir, out_dir):
    src = os.path.join(src_dir, SOURCE)
    arm_ob = x_import.load(src)
    xa = xanim.read(src)
    base = pose.from_clip(xa, 0)
    poses = []
    for f in range(FRAMES + 1):
        a = math.sin(2 * math.pi * f / FRAMES)
        p = pose.copy(base)
        pose.rotate(p, "Bip01_R_Forearm", "X", 40 * a)
        pose.rotate(p, "Bip01_R_Hand", "Z", 15 * a)
        pose.rotate(p, "Bip01_Head", "Y", 4 * a)
        pose.hold_prop(xa, p, base, "Bip01_Prop1", "Bip01_R_Hand")
        poses.append(p)
    pose.bake(arm_ob, xa, poses, NAME)
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, NAME + ".blend"))
    x_export.export(src, os.path.join(out_dir, NAME + ".x"), NAME, arm_ob)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    build(args[0], args[1])
