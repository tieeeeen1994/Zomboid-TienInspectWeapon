"""
Weapon-first posing: place the weapon in space, and the arms, head and torso follow.
Runs inside Blender (mathutils); used by the clips/*.py build scripts.

A clip is a list of keys, each a few numbers about the *weapon* and the body's attitude
(see Key below). For every frame, build() interpolates the keys and turns them into a full
pose on top of a vanilla base clip:

1. torso bones blended towards an optional second vanilla pose (the aim pose, for the
   "look down the sights" beat), then a forward lean and a slow breath;
2. neck and head turned to look at a point on the weapon;
3. the right arm solved by two-bone IK onto the weapon's grip, keeping the base clip's
   hand-to-weapon offset (Bip01_Prop1 relative to Bip01_R_Hand), and the left arm onto
   the weapon's second grip when the key says so (weapon-to-left-hand offset of the base
   or second pose);
4. Bip01_Prop1 put back on the right hand, since it is a child of Bip01, not of the hand.

All vectors are in character space, ch(right, up, forward), turned into the file's space
(right = -X, up = +Y, forward = -Z). Units are the file's: the character is 0.98 tall,
the shoulder is at 0.74 and an arm reaches 0.274 from the shoulder to the wrist.

Every weapon model in media/models_X/weapons has its long axis on local +Y from the grip
(muzzle, blade tip, bat end), and its flat side (the side of a gun, the flat of a blade)
facing local X. A key orients the weapon by where +Y points (`along`) and where +X faces
(`face`, default: towards the eyes), then turns it `roll` degrees about +Y.
"""

import math

from mathutils import Matrix, Quaternion, Vector

import pose
import x_import

RIGHT = Vector((-1.0, 0.0, 0.0))
UP = Vector((0.0, 1.0, 0.0))
FWD = Vector((0.0, 0.0, -1.0))
TORSO = ["Bip01_Spine", "Bip01_Spine1", "Bip01_Neck", "Bip01_Head", "Bip01_L_Clavicle", "Bip01_R_Clavicle"]
ARM = {s: ("Bip01_%s_UpperArm" % s, "Bip01_%s_Forearm" % s, "Bip01_%s_Hand" % s) for s in "LR"}
# The natural wrist: the hand's median angle (bend Y, bend Z) from the bind pose over all 1614
# vanilla Bob clips. A wrist bent WRIST_BEND degrees from it, or twisted WRIST_TWIST, is at the
# edge of what vanilla does (its 1st-99th percentiles) and of a human wrist.
WRIST_MEDIAN = {"R": (16.0, 5.0), "L": (18.0, -8.0)}
WRIST_BEND = (50.0, 45.0)
WRIST_TWIST = 80.0
# The elbow's swing about the shoulder-wrist line: at most SWIVEL_MAX degrees from the base
# pose's elbow, costing as much as a wrist at its edge at SWIVEL_SOFT. Each frame takes its own
# best swing (no history), so a raise ends exactly on its hold's first frame.
SWIVEL_MAX = 80
SWIVEL_SOFT = 60.0
# A relaxed elbow stays low: lifting it above ELBOW_LOW (height from the shoulder, the upper arm
# is 0.14 long) costs as much as a wrist at its edge for every further ELBOW_LIFT.
ELBOW_LOW = -0.08
ELBOW_LIFT = 0.04


def soft_limit(v, limit, knee=0.75):
    """v unchanged up to knee * limit, then easing (tanh, same slope at the knee) towards limit."""
    k = knee * limit
    a = abs(v)
    if a <= k:
        return v
    return math.copysign(k + (limit - k) * math.tanh((a - k) / (limit - k)), v)


def ch(right, up, forward):
    return RIGHT * right + UP * up + FWD * forward


def rot_of(m):
    return m.to_3x3().normalized()


def with_rot(m, rot3):
    return Matrix.LocRotScale(m.translation, rot3.to_quaternion(), None)


def weapon_matrix(pos, along, face, roll=0.0):
    y = along.normalized()
    x = face - y * face.dot(y)
    if x.length < 1e-6:
        x = UP.cross(y)
    x.normalize()
    if roll:
        x = Quaternion(y, math.radians(roll)) @ x
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed()
    return Matrix.LocRotScale(pos, m.to_quaternion(), None)


class Key:
    """One beat of a clip. Anything left None is carried from the previous key.

    frame    frame number
    pos      the grip (Prop1 origin) in character space, ch(right, up, forward)
    along    where the weapon's length points (character space direction)
    face     where its flat side faces; None = the eyes
    top      instead of face: where the weapon's top (sights) points (Rig(top=...) says
             which local axis that is), e.g. UP for a gun held level
    roll     degrees about the length, applied after face
    turn     degrees the forearm turns the weapon (pronation / supination: about the forearm's
             axis through the wrist, the hand's natural angle assumed), applied last. The way
             to show a blade's two faces: a roll about a blade held square to the forearm
             could only come from the wrist bending
    wrist    (bend Y, bend Z) degrees from the natural wrist, either None: the weapon is turned
             about the wrist until the solved hand has that bend, the grip kept at pos. (0, 0)
             or (None, 0) says "hold it as a relaxed hand would" instead of aiming it exactly
    look     0..1, how far the head turns to the weapon's point of interest
    lean     degrees of forward lean of the spine
    aux      0..1 blend of the torso towards the second pose (aim)
    support  0..1 left hand on the weapon (IK) instead of the base clip's left arm
    elbow    extra outward push of the elbows (character units)
    ease     True: pause here (zero velocity through this key)
    at_aux   True: take the weapon's place from the second pose instead of pos/along/face,
             lowered by `drop` and pitched down by `pitch` degrees
    """

    def __init__(self, frame, pos=None, along=None, face=None, top=None, roll=None, look=None, lean=None,
                 aux=None, support=None, elbow=None, ease=False, at_aux=False, drop=0.0, pitch=0.0, turn=None,
                 wrist=None):
        self.frame = frame
        self.pos, self.along, self.face, self.top, self.roll, self.turn = pos, along, face, top, roll, turn
        self.look, self.lean, self.aux, self.support, self.elbow = look, lean, aux, support, elbow
        self.ease, self.at_aux, self.drop, self.pitch = ease, at_aux, drop, pitch
        self.wrist = wrist


def _hermite(keys, values, frame, period=None):
    """Cubic Hermite through (key.frame, value); finite-difference tangents, 0 at ease keys.
    values are Vectors (or floats wrapped in 1-Vectors). period: loop length for a cycle."""
    n = len(keys)
    times = [k.frame for k in keys]
    if period:
        frame = (frame - times[0]) % period + times[0]
    else:
        if frame <= times[0]:
            return values[0].copy()
        if frame >= times[-1]:
            return values[-1].copy()

    def at(i):
        if period:
            wrap, j = divmod(i, n)
            return times[j] + wrap * period, values[j], keys[j].ease
        j = max(0, min(n - 1, i))
        return times[j], values[j], keys[j].ease or i != j or j in (0, n - 1)

    i = 0
    while True:
        t0 = at(i)[0]
        t1 = at(i + 1)[0]
        if t0 <= frame <= t1 or (not period and i >= n - 2):
            break
        i += 1

    def tangent(j):
        tj, vj, ease = at(j)
        if ease:
            return vj * 0.0
        tp, vp, _ = at(j - 1)
        tn, vn, _ = at(j + 1)
        return (vn - vp) / max(1e-6, (tn - tp))

    t0, v0, _ = at(i)
    t1, v1, _ = at(i + 1)
    h = max(1e-6, t1 - t0)
    s = (frame - t0) / h
    m0, m1 = tangent(i) * h, tangent(i + 1) * h
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    return v0 * h00 + m0 * h10 + v1 * h01 + m1 * h11


class Rig:
    def __init__(self, xa, base, aux=None, poi=0.15, top=None, support_from_aux=False, weapon="Bip01_Prop1",
                 rest=None):
        """xa: the clip file (for its hierarchy); base: its pose (pose.from_clip);
        rest: the bind pose (x_import.rest_matrices of a clip read with its mesh), where the
        natural wrist is measured from; without it, the base pose's wrist is taken as natural;
        aux: a second pose (e.g. the aim clip's) or None; poi: how far along the weapon the
        eyes look (its middle, or the sights); top: +1 / -1 if the weapon's top (sights) is
        its local +Z / -Z (rifles +1, handguns -1), for keys that give `top`;
        support_from_aux: the left hand's place on the weapon always comes from the second
        pose (a handgun's idle left hand hangs at the side, so the base has none)."""
        self.support_from_aux = support_from_aux
        self.xa, self.base, self.poi, self.top_sign = xa, base, poi, top
        self.parent = {f.name: f.parent for f in x_import.bone_frames(xa)}
        w = pose.world(xa, base)
        self.w0 = w
        self.grip_r = w["Bip01_R_Hand"].inverted() @ w[weapon]
        self.support_base = w[weapon].inverted() @ w["Bip01_L_Hand"]
        self.weapon0 = w[weapon].copy()
        head = w["Bip01_Head"]
        self.head_fwd = (rot_of(head).inverted() @ FWD).normalized()
        self.eye_local = head.inverted() @ (head.translation + UP * 0.03 + FWD * 0.04)
        self.eye0 = head @ self.eye_local
        spine = rot_of(w["Bip01_Spine1"])
        self.pole_local = {}
        for s, (u, f, _) in ARM.items():
            self.pole_local[s] = spine.inverted() @ (w[f].translation - w[u].translation)
        self.aux = None
        if aux:
            # The aim poses turn the hips 31 degrees into a bladed stance. Blending the legs
            # there would slide the feet, so only the torso follows: Bip01_Spine is re-rooted
            # to keep the aim torso's world orientation on top of the base clip's hips.
            wa = pose.world(xa, aux)
            rr = pose.copy(aux)
            rr["Bip01_Spine"] = with_rot(base["Bip01_Spine"],
                                         rot_of(w["Bip01_Pelvis"]).inverted() @ rot_of(wa["Bip01_Spine"]))
            self.aux = rr
            self.support_aux = wa[weapon].inverted() @ wa["Bip01_L_Hand"]
            full = pose.copy(base)
            self.blend_local(full, rr, TORSO, 1.0)
            wf = pose.world(xa, full)
            self.weapon_aux = wf["Bip01_Spine1"] @ (wa["Bip01_Spine1"].inverted() @ wa[weapon])
        self.wrist_neutral = {}
        for s, (_, F, H) in ARM.items():
            if rest:
                y, z = WRIST_MEDIAN[s]
                bend = Quaternion(Vector((0.0, math.radians(y), math.radians(z))).normalized(),
                                  math.radians(math.hypot(y, z)))
                self.wrist_neutral[s] = (rest[F].inverted() @ rest[H]).to_quaternion() @ bend
            else:
                self.wrist_neutral[s] = base[H].to_quaternion()
        self.swivel_scale = 1.0
        self.swivels = []
        self.warnings = []
        self.wrist_warnings = []

    # ------------------------------------------------------------ small edits

    def set_world_rot(self, p, w, bone, rot3):
        parent = self.parent[bone]
        prot = rot_of(w[parent]) if parent else Matrix.Identity(3)
        p[bone] = with_rot(p[bone], prot.inverted() @ rot3)

    def turn(self, p, bone, q, w=None):
        """Turn a bone by world rotation q about its own joint."""
        w = w or pose.world(self.xa, p)
        self.set_world_rot(p, w, bone, q.to_matrix() @ rot_of(w[bone]))

    def blend_local(self, p, other, bones, t):
        if t <= 0:
            return
        for b in bones:
            la, lb = p[b], other[b]
            qa, qb = la.to_quaternion(), lb.to_quaternion()
            if qa.dot(qb) < 0:
                qb.negate()
            p[b] = Matrix.LocRotScale(la.translation.lerp(lb.translation, t), qa.slerp(qb, t), None)

    def lean(self, p, degrees, split=(("Bip01_Spine", 0.4), ("Bip01_Spine1", 0.6))):
        for bone, share in split:
            self.turn(p, bone, Quaternion(UP.cross(FWD).normalized(), math.radians(-degrees * share)))

    def look_at(self, p, target, influence, split=(("Bip01_Neck", 0.35), ("Bip01_Head", 0.65))):
        if influence <= 0:
            return
        for bone, share in split:
            w = pose.world(self.xa, p)
            head = w["Bip01_Head"]
            eye = head @ self.eye_local
            cur = rot_of(head) @ self.head_fwd
            want = (target - eye).normalized()
            q = cur.rotation_difference(want)
            self.turn(p, bone, Quaternion().slerp(q, influence * share / (1.0 if bone == "Bip01_Head" else 1.0)), w)

    # ------------------------------------------------------------ arms

    def solve_arm(self, p, side, target, pole_extra=Vector(), limit=0.0):
        """Two-bone IK: put side's hand at target (world matrix) with the elbow towards the
        base pose's elbow direction (in the chest's frame) plus pole_extra, then swung about
        the shoulder-wrist line to the angle that keeps the wrist most natural (see
        wrist_cost): a person turns a weapon over with the shoulder and elbow, not by
        bending the wrist. limit (0..1): then ease the wrist that far into its natural range
        (soft_limit), so the hand, and the weapon it holds, give way where a key asks too much."""
        U, F, H = ARM[side]
        w = pose.world(self.xa, p)
        S = w[U].translation
        l1 = p[F].translation.length
        l2 = p[H].translation.length
        T = target.translation
        d_vec = T - S
        d = d_vec.length
        dirv = d_vec / d
        reach = (l1 + l2) * 0.999
        if d > reach:
            self.warnings.append("%s hand short of its target by %.3f" % (side, d - reach))
            d = reach
        d = max(d, abs(l1 - l2) + 1e-3)
        a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        h = math.sqrt(max(0.0, l1 * l1 - a * a))
        spine = rot_of(w["Bip01_Spine1"])
        pole = spine @ self.pole_local[side] + pole_extra
        n = pole - dirv * pole.dot(dirv)
        if n.length < 1e-6:
            n = FWD.cross(dirv)
        n.normalize()

        def cost(deg):
            q = dict(p)
            nd = Quaternion(dirv, math.radians(deg)) @ n
            self._place(q, w, side, target, S, dirv, d, a, h, nd)
            lift = max(0.0, (dirv * a + nd * h).dot(UP) - ELBOW_LOW) / ELBOW_LIFT
            return self.wrist_cost(q, side) + (deg / SWIVEL_SOFT) ** 2 + lift * lift

        best = min(range(-SWIVEL_MAX, SWIVEL_MAX + 1, 4), key=cost)
        best = min((best + i * 0.25 for i in range(-16, 17)), key=cost) * self.swivel_scale
        self.swivels.append((side, best))
        self._place(p, w, side, target, S, dirv, d, a, h, Quaternion(dirv, math.radians(best)) @ n)
        y, z, tw = self.wrist_angles(p, side)
        if abs(y) > WRIST_BEND[0] or abs(z) > WRIST_BEND[1] or abs(tw) > WRIST_TWIST:
            self.wrist_warnings.append("%s wrist bend %.0f/%.0f twist %.0f" % (side, y, z, tw))
        if limit > 0:
            self.set_wrist(p, side, y + (soft_limit(y, WRIST_BEND[0]) - y) * limit,
                           z + (soft_limit(z, WRIST_BEND[1]) - z) * limit,
                           tw + (soft_limit(tw, WRIST_TWIST) - tw) * limit)

    def set_wrist(self, p, side, y, z, tw):
        """The inverse of wrist_angles: put the hand at these angles from the natural wrist."""
        bend = math.hypot(y, z)
        sw = Quaternion(Vector((0.0, y, z)) / bend, math.radians(bend)) if bend > 1e-9 else Quaternion()
        rel = sw @ Quaternion(Vector((1.0, 0.0, 0.0)), math.radians(tw))
        H = ARM[side][2]
        p[H] = with_rot(p[H], (self.wrist_neutral[side] @ rel).to_matrix())

    def wrist_angles(self, p, side):
        """The hand relative to the forearm, from the natural wrist: (bend Y, bend Z, twist),
        degrees. Twist is about the forearm (pronation / supination)."""
        rel = self.wrist_neutral[side].inverted() @ p[ARM[side][2]].to_quaternion()
        if rel.w < 0:
            rel.negate()
        tw = Quaternion((rel.w, rel.x, 0.0, 0.0))
        tw = tw.normalized() if tw.magnitude > 1e-9 else Quaternion()
        twist = math.degrees(2 * math.atan2(tw.x, tw.w))
        axis, ang = (rel @ tw.inverted()).to_axis_angle()
        if ang > math.pi:
            ang -= 2 * math.pi
        sw = axis * math.degrees(ang)
        return sw.y, sw.z, twist

    def wrist_cost(self, p, side):
        y, z, tw = self.wrist_angles(p, side)
        return (y / WRIST_BEND[0]) ** 2 + (z / WRIST_BEND[1]) ** 2 + (tw / WRIST_TWIST) ** 4

    def _place(self, p, w, side, target, S, dirv, d, a, h, n):
        """Pose side's arm for the elbow direction n (see solve_arm). The forearm only
        hinges, as in every vanilla clip; the hand takes the twist, as a forearm's
        pronation does (the skin is weighted for it; there are no twist bones)."""
        U, F, H = ARM[side]
        E = S + dirv * a + n * h
        P = S + dirv * d
        u1 = (E - S).normalized()
        f1 = (P - E).normalized()
        # bend the elbow (in the upper arm's frame) to the angle the solution needs
        x = Vector((1.0, 0.0, 0.0))
        fl = p[F]
        b0 = (rot_of(fl) @ x).normalized()
        k = x.cross(b0)
        if k.length < 1e-6:
            k = Vector((0.0, 1.0, 0.0))
        theta = math.acos(max(-1.0, min(1.0, u1.dot(f1))))
        theta0 = math.acos(max(-1.0, min(1.0, x.dot(b0))))
        fl_rot = Quaternion(k.normalized(), theta - theta0).to_matrix() @ rot_of(fl)
        b1 = fl_rot @ x

        def frame(a_, b_):
            a_ = a_.normalized()
            n_ = a_.cross(b_).normalized()
            return Matrix((a_, n_, a_.cross(n_))).transposed()

        up_rot = frame(u1, f1) @ frame(x, b1).transposed()
        self.set_world_rot(p, w, U, up_rot)
        p[F] = with_rot(p[F], fl_rot)
        # the hand takes the target's rotation (only this chain moved: no full world pass)
        wf = w[self.parent[U]] @ p[U] @ p[F]
        hand_world = Matrix.LocRotScale(P, target.to_quaternion(), None)
        p[H] = with_rot(p[H], rot_of(wf.inverted() @ hand_world))

    # ------------------------------------------------------------ frames

    def weapon_at(self, k, eye):
        if k["at_aux"] > 0.5 and self.aux:
            m = self.weapon_aux.copy()
            if k["pitch"]:
                m = Matrix.LocRotScale(m.translation, (Quaternion(UP.cross(FWD).normalized(), math.radians(-k["pitch"])) @ m.to_quaternion()), None)
            m.translation = m.translation - UP * k["drop"]
            return m
        if k["top"] is not None and self.top_sign:
            y = k["along"].normalized()
            z = k["top"] * self.top_sign
            z = (z - y * z.dot(y)).normalized()
            face = y.cross(z)
        else:
            face = k["face"] if k["face"] is not None else (eye - k["pos"])
        m = weapon_matrix(k["pos"], k["along"], face, k["roll"] or 0.0)
        if k["turn"]:
            # about the forearm's axis (in the hand's frame at the natural wrist) through the wrist
            axis = self.wrist_neutral["R"].inverted() @ Vector((1.0, 0.0, 0.0))
            m = m @ self.grip_r.inverted() @ Matrix.Rotation(math.radians(k["turn"]), 4, axis) @ self.grip_r
        return m

    def resolve(self, keys):
        """Fill every key's missing values from the previous key."""
        cur = dict(pos=self.weapon0.translation.copy(), along=rot_of(self.weapon0) @ Vector((0, 1, 0)),
                   face=rot_of(self.weapon0) @ Vector((1, 0, 0)), roll=0.0, look=0.0, lean=0.0, aux=0.0,
                   support=0.0, elbow=0.0, at_aux=0.0, drop=0.0, pitch=0.0, top=None, turn=0.0, wrist=None)
        out = []
        for k in keys:
            for name in ("pos", "along", "face", "top", "roll", "turn", "wrist", "look", "lean", "aux", "support",
                         "elbow"):
                v = getattr(k, name)
                if v is not None:
                    cur[name] = v
            cur["at_aux"] = 1.0 if k.at_aux else 0.0
            cur["drop"], cur["pitch"] = k.drop, k.pitch
            out.append(dict(cur))
        return out

    def build(self, keys, frames, period=None, breath=(0.8, None), from_base=False):
        """One pose per frame 0..frames-1 (or 0..frames for a non-looping clip).

        from_base: the first key is exactly the base pose (the raise starts from idle)."""
        vals = self.resolve(keys)
        # weapon placement per key, as (pos, quaternion) with one hemisphere
        mats = []
        for i, v in enumerate(vals):
            if i == 0 and from_base:
                mats.append(self.weapon0.copy())
            else:
                m = self.weapon_at(v, self.eye0)
                if v["wrist"] and not v["at_aux"]:
                    m = self.settle(m, v)
                mats.append(m)
        q_ref = mats[0].to_quaternion()
        rotvecs, positions = [], []
        prev = None
        for m in mats:
            q = q_ref.inverted() @ m.to_quaternion()
            if prev is not None and q.dot(prev) < 0:
                q.negate()
            prev = q
            axis, ang = q.to_axis_angle()
            if ang > math.pi:
                ang -= 2 * math.pi
            rotvecs.append(axis * ang)
            positions.append(m.translation.copy())
        scal = {name: [Vector((v[name], 0.0)) for v in vals] for name in ("look", "lean", "aux", "support", "elbow")}
        count = frames if period else frames + 1
        poses = []
        for f in range(count):
            pos = _hermite(keys, positions, f, period)
            rv = _hermite(keys, rotvecs, f, period)
            q = q_ref @ (Quaternion(rv.normalized(), rv.length) if rv.length > 1e-9 else Quaternion())
            W = Matrix.LocRotScale(pos, q, None)
            s = {name: _hermite(keys, scal[name], f, period)[0] for name in scal}
            # a raise starts on the base pose's elbow and swings it in on the way up
            t = f / float(frames) if from_base else 1.0
            self.swivel_scale = t * t * (3 - 2 * t)
            poses.append(self.pose_for(W, s, f, breath, period or frames))
        return poses

    def settle(self, W, v, rounds=4):
        """The weapon W turned about the wrist until the right wrist has v["wrist"]'s bend,
        its grip kept where W's is (a few rounds: moving the grip moves the wrist a little)."""
        pos = W.translation.copy()
        s = {name: v[name] for name in ("look", "lean", "aux", "support", "elbow")}
        scale, n, nw = self.swivel_scale, len(self.swivels), len(self.wrist_warnings)
        self.swivel_scale = 1.0
        for _ in range(rounds):
            p = self.pose_for(W, s, 0, (0, None), 1)
            y, z, tw = self.wrist_angles(p, "R")
            want_y, want_z = v["wrist"]
            self.set_wrist(p, "R", y if want_y is None else want_y, z if want_z is None else want_z, tw)
            W = pose.world(self.xa, p)["Bip01_R_Hand"] @ self.grip_r
            W.translation = pos
        self.swivel_scale = scale
        del self.swivels[n:]
        del self.wrist_warnings[nw:]
        return W

    def pose_for(self, W, s, frame, breath, period):
        p = pose.copy(self.base)
        if self.aux and s["aux"] > 0:
            self.blend_local(p, self.aux, TORSO, min(1.0, s["aux"]))
        lean = s["lean"]
        amp, per = breath
        if amp:
            per = per or period
            lean += amp * math.sin(2 * math.pi * frame / per)
        if lean:
            self.lean(p, lean)
        self.look_at(p, W @ Vector((0.0, self.poi, 0.0)), max(0.0, min(1.0, s["look"])))
        out = RIGHT * s["elbow"]
        # vanilla's aim pose is trusted as it is: the wrist limit fades out towards it
        limit = 1.0 - max(0.0, min(1.0, s["aux"]))
        self.solve_arm(p, "R", W @ self.grip_r.inverted(), pole_extra=out + UP * -0.05, limit=limit)
        W = pose.world(self.xa, p)["Bip01_R_Hand"] @ self.grip_r  # where the weapon ended up
        sup = max(0.0, min(1.0, s["support"]))
        if sup > 0:
            free = pose.copy(p)
            if self.aux and self.support_from_aux:
                offset = self.support_aux
            elif self.aux and s["aux"] > 0:
                t = min(1.0, s["aux"])
                a, b = self.support_base, self.support_aux
                qa, qb = a.to_quaternion(), b.to_quaternion()
                if qa.dot(qb) < 0:
                    qb.negate()
                offset = Matrix.LocRotScale(a.translation.lerp(b.translation, t), qa.slerp(qb, t), None)
            else:
                offset = self.support_base
            self.solve_arm(p, "L", W @ offset, pole_extra=-out + UP * -0.05)
            if sup < 1:
                solved = pose.copy(p)
                p.update(free)
                self.blend_local(p, solved, ARM["L"], sup)
        w = pose.world(self.xa, p)
        p["Bip01_Prop1"] = w["Bip01"].inverted() @ (w["Bip01_R_Hand"] @ self.grip_r)
        return p
