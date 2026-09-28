"""
Load a vanilla Project Zomboid .x animation into Blender: the Bob skeleton, the skinned
body mesh and the clip as an action. Runs inside Blender:

    blender -b -P scripts/anim/x_import.py -- <clip.x> <out.blend>

or from Blender's Text Editor (set ARGS below). Everything is built so x_export.py can
write the result back out bit-for-bit compatible with the game; see xanim.py for the file
conventions and README.md in this folder for the workflow.

How the file's world maps onto Blender's:

- Armature space *is* the .x file's space (Y up, character facing -Z, 1 unit = 1 m,
  a character about 0.98 tall). Export reads armature-space matrices, so whatever the
  armature object's own transform is, it never reaches the game.
- That space is left-handed: Bip01_R_Hand sits at -X, which a right-handed viewer shows
  as the character's left. The armature object therefore gets the matrix that swaps Y
  and Z (determinant -1). That both stands the character up (Z up, facing -Y, so
  Blender's Front view looks at the face) and un-mirrors it, so R_ bones are on the
  character's right as they should be.
- The rest pose is the mesh's bind pose (the inverse of each SkinWeights offset matrix,
  arms out). Bones with no skin weights (Dummy01, Bip01, Bip01_Prop1/2, Translation_Data,
  the Nub bones) rest where the file's frames put them relative to their parent.
- Biped bones point down their local X axis; Blender bones point down Y. Each Blender
  bone is the file's bone times C (a 90 degree turn about Z taking Blender's Y onto the
  file's X), so bones draw along the limbs and a twist of the forearm or hand is a roll
  about the bone. x_export.py takes C back off.
- Frame f of the action is tick f * (AnimTicksPerSecond / 30); vanilla keys every
  160 ticks at 4800 ticks per second, which is 30 fps.
"""

import os
import sys

import bpy
from mathutils import Matrix, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xanim  # noqa: E402

ARGS = []  # set when running from the Text Editor: [clip_path, out_blend_path]

FPS = 30
# Blender bone = file bone @ C
C = Matrix(((0, 1, 0, 0), (-1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
# Armature object: swap Y and Z (stand up and un-mirror)
OBJECT_MATRIX = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def m4(rows):
    return Matrix([list(r) for r in rows])


def orthonormal(m):
    loc, rot, _ = m.decompose()
    return Matrix.LocRotScale(loc, rot, None)


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials):
        for item in list(coll):
            coll.remove(item)


def rest_matrices(xa):
    """World rest matrix (file bones, no C) of every non-mesh frame."""
    skin = xa.mesh[2] if xa.mesh else {}
    rest = {}
    for f in xa.frames:
        if f.name in skin:
            rest[f.name] = orthonormal(m4(skin[f.name][2]).inverted())
        elif f.parent and f.parent in rest:
            rest[f.name] = orthonormal(rest[f.parent] @ m4(f.matrix))
        else:
            rest[f.name] = orthonormal(m4(f.matrix))
    return rest


def bone_frames(xa):
    """The frames that are bones: everything but the frame holding the mesh."""
    return [f for f in xa.frames if f.name != "Body"]


def build_armature(xa, name="Bob"):
    frames = bone_frames(xa)
    rest = rest_matrices(xa)
    arm = bpy.data.armatures.new(name)
    arm.display_type = "STICK"
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = OBJECT_MATRIX
    ob.show_in_front = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    children = {}
    for f in frames:
        children.setdefault(f.parent, []).append(f.name)
    for f in frames:
        length = 0.0
        for c in children.get(f.name, []):
            local = rest[f.name].inverted() @ rest[c]
            length = max(length, local.translation.x)
        if length < 0.02:
            length = 0.08 if "Prop" in f.name else 0.04
        eb = arm.edit_bones.new(f.name)
        eb.head = (0, 0, 0)
        eb.tail = (0, length, 0)
        eb.matrix = rest[f.name] @ C
        if f.parent and f.parent in arm.edit_bones:
            eb.parent = arm.edit_bones[f.parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


def build_mesh(xa, arm_ob):
    verts, faces, skin = xa.mesh
    me = bpy.data.meshes.new("Body")
    me.from_pydata([tuple(v) for v in verts], [], [tuple(reversed(f)) for f in faces])
    me.update()
    ob = bpy.data.objects.new("Body", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = arm_ob
    for bone, (idx, wts, _) in skin.items():
        vg = ob.vertex_groups.new(name=bone)
        for i, w in zip(idx, wts):
            vg.add([i], w, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_ob
    mat = bpy.data.materials.new("Body")
    mat.diffuse_color = (0.72, 0.64, 0.56, 1.0)
    me.materials.append(mat)
    return ob


def pose_world(xa, t):
    """World matrix (file bones, no C) of every bone at tick t, from the clip's tracks."""
    tracks = {tr.bone: tr for tr in xa.tracks}
    out = {}
    for f in bone_frames(xa):
        tr = tracks.get(f.name)
        if tr:
            s = xanim.sample(tr, "S", t) or [1, 1, 1]
            q = xanim.sample(tr, "R", t) or (1, 0, 0, 0)
            p = xanim.sample(tr, "T", t) or [0, 0, 0]
            local = m4(xanim.srt_to_mat4(s, q, p))
        else:
            local = m4(f.matrix)
        out[f.name] = out[f.parent] @ local if f.parent in out else local
    return out


def apply_pose(arm_ob, world):
    """Set every pose bone's matrix_basis so its armature-space pose is world[name] @ C."""
    bones = arm_ob.data.bones
    basis = {}
    for b in bones:
        pose_b = world[b.name] @ C
        if b.parent:
            parent_pose_b = world[b.parent.name] @ C
            basis[b.name] = b.matrix_local.inverted() @ b.parent.matrix_local @ parent_pose_b.inverted() @ pose_b
        else:
            basis[b.name] = b.matrix_local.inverted() @ pose_b
    for pb in arm_ob.pose.bones:
        pb.matrix_basis = basis[pb.name]


def import_action(xa, arm_ob):
    step = xa.ticks_per_second / float(FPS)
    times = set()
    for tr in xa.tracks:
        times.update(tr.S)
        times.update(tr.R)
        times.update(tr.T)
    times = sorted(times)
    arm_ob.animation_data_create()
    action = bpy.data.actions.new(xa.clip_name or "Clip")
    arm_ob.animation_data.action = action
    prev = {}
    for t in times:
        apply_pose(arm_ob, pose_world(xa, t))
        frame = t / step
        for pb in arm_ob.pose.bones:
            q = pb.rotation_quaternion.copy()
            if pb.name in prev:
                q.make_compatible(prev[pb.name])
            pb.rotation_quaternion = q
            prev[pb.name] = q
            for path in ("location", "rotation_quaternion", "scale"):
                pb.keyframe_insert(path, frame=frame, group=pb.name)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 0
    scene.frame_end = int(round(times[-1] / step)) if times else 0
    return action


def load(path, name=None):
    xa = xanim.read(path, with_mesh=True)
    clear_scene()
    arm_ob = build_armature(xa)
    if xa.mesh:
        build_mesh(xa, arm_ob)
    action = import_action(xa, arm_ob)
    if name:
        action.name = name
    arm_ob["zf_source_x"] = os.path.abspath(path)
    bpy.context.scene.frame_set(0)
    return arm_ob


def main(argv):
    clip = argv[0]
    out = argv[1] if len(argv) > 1 else None
    load(clip)
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out))
        print("[x_import] saved", out)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ARGS
    if args:
        main(args)
