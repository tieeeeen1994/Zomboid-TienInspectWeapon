"""
Render still frames of the armature's action, with a weapon in the right hand, so a pose
can be checked without starting the game. Runs inside Blender:

    blender -b <file.blend> -P scripts/anim/x_preview.py -- <out_dir> [frames] [weapon.x]

[frames] is a comma list ("0,20,40") or "every:N" (default every:10). [weapon.x] is a
static model from media/models_X (default weapons/1handed/Machete.x); its vertices are in
Bip01_Prop1's space, which is where the game draws a right-hand weapon that has no
Bip01_Prop1 attachment in its model script (the machete has none).

Two views per frame, <out_dir>/<view>_<frame>.png: "front" (three quarters from the
character's front right) and "side" (from their right). sheet.py (system python3, needs
Pillow) lays them out as one image.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xanim  # noqa: E402
from x_import import C  # noqa: E402

ARGS = []  # set when running from the Text Editor: [out_dir, frames, weapon_x]
MEDIA = os.path.expanduser(
    "~/Library/Application Support/Steam/steamapps/common/ProjectZomboid/"
    "Project Zomboid.app/Contents/Java/media")
VIEWS = {
    # name: (camera location, look-at), Blender space: Z up, character faces -Y
    "front": ((-0.95, -1.55, 0.85), (0.0, 0.0, 0.55)),
    "side": ((-1.8, -0.05, 0.75), (0.0, 0.0, 0.55)),
}


def find_armature():
    for ob in bpy.data.objects:
        if ob.type == "ARMATURE":
            return ob
    raise RuntimeError("no armature in this file")


def static_mesh(path, name):
    xa = xanim.read(path, with_mesh=True)
    verts, faces, _ = xa.mesh
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(reversed(f)) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (0.25, 0.27, 0.3, 1.0)
    me.materials.append(mat)
    return ob


def attach_to_bone(ob, arm_ob, bone_name):
    """Parent ob so its local space is the *file's* frame of bone_name."""
    bone = arm_ob.data.bones[bone_name]
    ob.parent = arm_ob
    ob.parent_type = "BONE"
    ob.parent_bone = bone_name
    ob.matrix_parent_inverse = Matrix.Translation((0, -bone.length, 0)) @ C.inverted()
    ob.matrix_basis = Matrix.Identity(4)


def camera(name, loc, target):
    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = 1.35
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    direction = Vector(target) - Vector(loc)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return ob


def setup_render(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 420
    scene.render.resolution_y = 520
    scene.render.film_transparent = False
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_cavity = True
    shading.show_object_outline = True
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.color = (0.16, 0.17, 0.19)


def parse_frames(spec, scene):
    if spec.startswith("every:"):
        n = int(spec.split(":")[1])
        frames = list(range(scene.frame_start, scene.frame_end + 1, n))
        if frames[-1] != scene.frame_end:
            frames.append(scene.frame_end)
        return frames
    return [int(f) for f in spec.split(",") if f.strip()]


def render(out_dir, frames, weapon=None, offset=0, arm_ob=None):
    """Render each frame's views to out_dir/<view>_<offset + frame>.png."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    arm_ob = arm_ob or find_armature()
    for ob in [o for o in bpy.data.objects if o.name.startswith(("Weapon", "Cam_"))]:
        bpy.data.objects.remove(ob, do_unlink=True)
    if weapon and weapon != "none":
        attach_to_bone(static_mesh(weapon, "Weapon"), arm_ob, "Bip01_Prop1")
    setup_render(scene)
    cams = {name: camera("Cam_" + name, loc, tgt) for name, (loc, tgt) in VIEWS.items()}
    for frame in frames:
        scene.frame_set(frame)
        for name, cam in cams.items():
            scene.camera = cam
            scene.render.filepath = os.path.join(out_dir, "%s_%03d.png" % (name, offset + frame))
            bpy.ops.render.render(write_still=True)


def main(argv):
    out_dir = os.path.abspath(argv[0])
    spec = argv[1] if len(argv) > 1 else "every:10"
    weapon = argv[2] if len(argv) > 2 else os.path.join(MEDIA, "models_X/weapons/1handed/Machete.x")
    render(out_dir, parse_frames(spec, bpy.context.scene), weapon)
    print("[x_preview] rendered to", out_dir)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ARGS
    if args:
        main(args)
