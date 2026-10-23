"""
Body clearance for a baked clip (Blender): how deep the forearms, hands or a held weapon sink into the body.
Previews hide it from some angles, so measure it: a hand or a gun inside the chest is the one mistake a viewer
never forgives.

    body = clearance.Body(arm_ob)                 # after pose.bake
    worst = body.check(frames, extra={"gun": [ob, ...]})
    # {"L": (depth, frame), "R": (depth, frame), "gun": (depth, frame)}

The body is the skinned mesh's chest, neck and head (every face whose vertices all belong mostly to BODY): Bob's
lower half is a dress, and hands hanging at the thighs or a lowered gun are inside it in vanilla's own idles. A
point is inside when most of RAYS cross the faces an odd number of times (a ray leaving through the open waist or a
shoulder opening is outvoted; below the waist the horizontal rays miss the chest altogether); its depth is the
distance to the nearest body face. Arms are measured along their bones with a limb's radius (SEGMENTS; the elbow
60% of the upper arm, where an arm reaching across the chest goes in), the weapon by its vertices. A nearest-face normal test was tried first and read
backwards on this mesh (the dress flares out at the waist, the open edges have no back).
"""

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

BODY = {"Bip01_Spine", "Bip01_Spine1", "Bip01_Neck", "Bip01_Head", "Bip01_L_Clavicle", "Bip01_R_Clavicle",
        "Bip01_BackPack"}
# the arm's centre line, (from bone, to bone, start fraction, limb radius): the skin overlaps the chest's side even in
# vanilla's idle, so the arms are measured by their bones, a radius out
SEGMENTS = [("UpperArm", "Forearm", 0.4, 0.022), ("Forearm", "Hand", 0.0, 0.018), ("Hand", "Finger1", 0.0, 0.014)]
RAYS = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1))]


class Body:
    def __init__(self, arm_ob, bones=None):
        """bones: the vertex groups that make the body (default BODY: chest, neck, head; pass BODY | {"Bip01_Pelvis"}
        to check a weapon held low against the belly and hips too)."""
        bones = bones or BODY
        # the skinned body (props parented to bones are children of the armature too)
        self.body = next(o for o in arm_ob.children if o.type == 'MESH' and len(o.vertex_groups))
        names = {vg.index: vg.name for vg in self.body.vertex_groups}
        major = []
        for v in self.body.data.vertices:
            g = max(v.groups, key=lambda e: e.weight, default=None)
            major.append(names[g.group] if g else None)
        self.polys = [tuple(p.vertices) for p in self.body.data.polygons
                      if all(major[i] in bones for i in p.vertices)]
        self.arm_ob = arm_ob

    def segments(self):
        """{"L" / "R": [(point, radius), ...]} along each arm's bones at the current frame."""
        mw, pb = self.arm_ob.matrix_world, self.arm_ob.pose.bones
        out = {}
        for side in "LR":
            pts = []
            for a, b, t0, r in SEGMENTS:
                pa = mw @ pb["Bip01_%s_%s" % (side, a)].head
                pc = mw @ pb["Bip01_%s_%s" % (side, b)].head
                pts += [(pa.lerp(pc, t0 + (1 - t0) * k / 8.0), r) for k in range(9)]
            out[side] = pts
        return out

    def frame(self, frame, extra=None):
        """{"L": depth, "R": depth, name: depth for each extra list of mesh objects} at one frame."""
        bpy.context.scene.frame_set(frame)
        return self.now(extra)

    def now(self, extra=None):
        """The same for the armature as it stands (e.g. after x_import.apply_pose, to try poses without baking)."""
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.body.evaluated_get(dg).to_mesh()
        mw = self.body.matrix_world
        verts = [mw @ v.co for v in ev.vertices]
        self.body.evaluated_get(dg).to_mesh_clear()
        tree = BVHTree.FromPolygons(verts, self.polys)
        out = {side: max(sink(tree, p, r) for p, r in pts) for side, pts in self.segments().items()}
        for name, obs in (extra or {}).items():
            pts = []
            for ob in obs:
                ow = ob.matrix_world
                pts += [ow @ v.co for v in ob.data.vertices]
            out[name] = depth(tree, pts)
        return out

    def check(self, frames, extra=None):
        """The deepest point per part over `frames`: {part: (depth, frame)}."""
        worst = {}
        for f in frames:
            for k, d in self.frame(f, extra).items():
                if k not in worst or d > worst[k][0]:
                    worst[k] = (d, f)
        return worst


def crossings(tree, p, d):
    n, o = 0, p
    while n < 40:
        hit = tree.ray_cast(o, d)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + d * 1e-5
    return n


def inside(tree, p):
    return sum(crossings(tree, p, d) % 2 for d in RAYS) * 2 > len(RAYS)


def sink(tree, p, radius):
    """How far a limb of this radius around p goes into the body."""
    d = tree.find_nearest(p)[3]
    return d + radius if inside(tree, p) else max(0.0, radius - d)


def depth(tree, points):
    deepest = 0.0
    for p in points:
        if inside(tree, p):
            deepest = max(deepest, tree.find_nearest(p)[3])
    return deepest


def gap(tree, points):
    """The mean distance from points outside the body to its nearest face (how far a held thing stands off)."""
    ds = [tree.find_nearest(p)[3] for p in points if not inside(tree, p)]
    return sum(ds) / len(ds) if ds else 0.0


def report(tag, worst, threshold=0.004):
    """One line per part deeper than threshold (character units; the chest is about 0.18 deep)."""
    for k, (d, f) in sorted(worst.items()):
        if d > threshold:
            print("%s: %s into the body by %.3f (frame %d)" % (tag, k, d, f))
