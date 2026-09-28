"""
Helpers for authoring clips in code, inside Blender. A pose is a dict of *file-space*
local matrices (bone relative to its parent, exactly what an .x key holds), so every
edit is made in the game's own terms; bake() turns a list of poses into keys on the
armature through x_import's mapping.

    base = pose.from_clip(xa, tick)           # a vanilla clip's pose at a tick
    p = pose.copy(base)
    pose.rotate(p, "Bip01_R_Forearm", "X", 30)  # degrees about the bone's own axis
    pose.hold_prop(p, base, "Bip01_Prop1", "Bip01_R_Hand")  # keep the weapon in the hand
    pose.bake(arm_ob, xa, [p0, p1, ...], "ClipName")

Biped axes (the file's, not Blender's): every bone's local X points down the bone to its
child, so "X" is a twist (forearm roll, spine twist) and "Y" / "Z" bend it.
"""

import math

import bpy
from mathutils import Matrix

import x_import


def from_clip(xa, tick):
    tracks = {tr.bone: tr for tr in xa.tracks}
    out = {}
    for f in x_import.bone_frames(xa):
        tr = tracks.get(f.name)
        if tr:
            import xanim
            s = xanim.sample(tr, "S", tick) or [1, 1, 1]
            q = xanim.sample(tr, "R", tick) or (1, 0, 0, 0)
            t = xanim.sample(tr, "T", tick) or [0, 0, 0]
            out[f.name] = x_import.m4(xanim.srt_to_mat4(s, q, t))
        else:
            out[f.name] = x_import.m4(f.matrix)
    return out


def copy(p):
    return {k: v.copy() for k, v in p.items()}


def world(xa, p):
    out = {}
    for f in x_import.bone_frames(xa):
        out[f.name] = out[f.parent] @ p[f.name] if f.parent in out else p[f.name].copy()
    return out


def rotate(p, bone, axis, degrees):
    """Turn a bone about its own local axis (in its parent's frame after the turn)."""
    p[bone] = p[bone] @ Matrix.Rotation(math.radians(degrees), 4, axis)


def hold_prop(xa, p, base, prop, hand):
    """Move prop so it keeps the offset from hand it has in base."""
    wb = world(xa, base)
    grip = wb[hand].inverted() @ wb[prop]
    w = world(xa, p)
    parent = next(f.parent for f in xa.frames if f.name == prop)
    p[prop] = w[parent].inverted() @ w[hand] @ grip


def bake(arm_ob, xa, poses, name, start=0):
    """Key one pose per frame from start; replaces the armature's action."""
    ad = arm_ob.animation_data or arm_ob.animation_data_create()
    old = ad.action
    ad.action = bpy.data.actions.new(name)
    if old:
        bpy.data.actions.remove(old)
    prev = {}
    for i, p in enumerate(poses):
        x_import.apply_pose(arm_ob, world(xa, p))
        for pb in arm_ob.pose.bones:
            q = pb.rotation_quaternion.copy()
            if pb.name in prev:
                q.make_compatible(prev[pb.name])
            pb.rotation_quaternion = q
            prev[pb.name] = q
            for path in ("location", "rotation_quaternion", "scale"):
                pb.keyframe_insert(path, frame=start + i, group=pb.name)
    scene = bpy.context.scene
    scene.frame_start = start
    scene.frame_end = start + len(poses) - 1
    scene.frame_set(start)
    return ad.action
