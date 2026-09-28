"""
Write the armature's current action out as a Project Zomboid .x clip. Runs inside Blender:

    blender -b <file.blend> -P scripts/anim/x_export.py -- <template.x> <out.x> <ClipName>

<template.x> is a vanilla clip from media/anims_X/Bob. Everything of it before its
AnimTicksPerSecond (the frame hierarchy and the skinned body mesh, which the game needs
to accept the file at all) is copied as is; the AnimationSet is replaced by this action,
one key per frame from the scene's frame_start to frame_end, for every bone of the
template's hierarchy.

It reads each bone's *evaluated* armature-space pose (pose_bone.matrix), so constraints
are baked in: a Child Of that keeps Bip01_Prop1 in the right hand, IK, anything.
The inverse of x_import.py's mapping: file bone = Blender bone @ C^-1, and each key is
the bone relative to its parent in the file's hierarchy.

<ClipName> becomes the AnimationSet's name, which is the name <m_AnimName> uses. Keep the
file name the same (<ClipName>.x) so the two never disagree.
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xanim  # noqa: E402
from x_import import C, FPS  # noqa: E402

ARGS = []  # set when running from the Text Editor: [template_x, out_x, clip_name]
C_INV = C.inverted()


def find_armature():
    for ob in bpy.data.objects:
        if ob.type == "ARMATURE":
            return ob
    raise RuntimeError("no armature in this file")


def export(template, out_path, clip_name, arm_ob=None):
    arm_ob = arm_ob or find_armature()
    tmpl = xanim.read(template)
    frames = [f for f in tmpl.frames if f.name != "Body"]
    missing = [f.name for f in frames if f.name not in arm_ob.pose.bones]
    if missing:
        raise RuntimeError("armature lacks bones of the template: %s" % ", ".join(missing))
    scene = bpy.context.scene
    step = tmpl.ticks_per_second // FPS
    tracks = {f.name: xanim.Track(f.name) for f in frames}
    prev_q = {}
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        tick = (frame - scene.frame_start) * step
        world = {f.name: arm_ob.pose.bones[f.name].matrix @ C_INV for f in frames}
        for f in frames:
            local = world[f.parent].inverted() @ world[f.name] if f.parent in world else world[f.name]
            s, q, t = xanim.mat4_to_srt([list(r) for r in local])
            if f.name in prev_q and sum(a * b for a, b in zip(q, prev_q[f.name])) < 0:
                q = tuple(-c for c in q)
            prev_q[f.name] = q
            tr = tracks[f.name]
            tr.S[tick], tr.R[tick], tr.T[tick] = s, q, t
    xanim.write_clip(template, out_path, clip_name, [tracks[f.name] for f in frames], tmpl.ticks_per_second)
    print("[x_export] wrote %s: %s, %d frames (%.2f s)" % (
        out_path, clip_name, scene.frame_end - scene.frame_start + 1,
        (scene.frame_end - scene.frame_start) / float(FPS)))


def main(argv):
    export(argv[0], argv[1], argv[2])


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ARGS
    if args:
        main(args)
