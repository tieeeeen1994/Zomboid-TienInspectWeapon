#!/usr/bin/env python3
"""
Bake what the game shows for a Default mode inspection into one clip, so the whole sequence
(idle, the looting raise, the hand-off, the hold) can be rendered by x_preview.py and looked at
without starting the game. System python3, no dependencies:

    python3 scripts/anim/sequence.py <kind> <out.x> [raise_seconds] [hold_seconds]

<kind> is 1H, 2H, Handgun or Rifle (the hold clip and the idle it starts from). [raise_seconds]
is how long the raise action lasts in game (InspectSeconds, default 0.5; a firearm takes 1.25x,
each Maintenance level takes 2.5% off). It prints the frame the hold starts on and the weapon
model to render with, and writes <out>_phases.txt: "frame looting_weight hold_weight" per frame.

It copies the engine's blending (decompiled, 42.20):
- AnimationPlayer.updateBoneAnimationTransform_Internal walks the live tracks newest first; each
  takes min(weight, what is left of 1), positions summed by weight, rotations by successive slerp
  (weight / (weight + total so far)).
- LiveAnimNode blends a node in over its m_BlendTime and out over its blend-out time (m_BlendTime
  when there is no m_BlendOutTime), both through PZMath.lerpFunc_EaseOutInQuad, starting from
  the raw weight it had.
- The actions state is a substate, so the idle (the parent layer) keeps running underneath at
  full weight and fills whatever the action nodes leave.
The node values below are the ones in media/AnimSets/player/actions; keep them in step.

It shows the blend, not the game's frame-to-frame behaviour: anything that goes wrong only while
the game runs (a node restarting, a variable flickering) will not appear here.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xanim  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# the game's media folder, as in x_preview.py; set PZ_MEDIA to override
MEDIA = os.environ.get("PZ_MEDIA") or (
    "C:/Program Files (x86)/Steam/steamapps/common/ProjectZomboid/media" if os.name == "nt" else
    os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/ProjectZomboid/"
                       "Project Zomboid.app/Contents/Java/media"))
BOB = os.path.join(MEDIA, "anims_X", "Bob")
MOD_BOB = os.path.join(REPO, "Contents", "mods", "TienInspectWeapon", "42", "media", "anims_X", "Bob")

# kind: (the idle the character stands in, the preview weapon), as in clips/inspect.py
KINDS = {
    "1H": ("Bob_Idle", "weapons/1handed/Machete.x"),
    "2H": ("Bob_IdleBat", "weapons/2handed/Baseballbat.x"),
    "Handgun": ("Bob_IdleHandgun", "weapons/firearm/M9_Pistol.x"),
    "Rifle": ("Bob_IdleRifle", "weapons/firearm/MSR788_Rifle.x"),
}
RAISE_CLIP = "Bob_IdleLooting_Mid"
FPS = 30
TICKS_PER_FRAME = 160
LEAD_IN = 0.3                                              # seconds of idle before the key press
RAISE_BLEND_IN, RAISE_BLEND_OUT, RAISE_SPEED = 0.40, 0.40, 0.65  # TienInspectWeapon.xml
HOLD_BLEND_IN = 0.30                                       # TienInspectWeaponHold*.xml


def ease(x):
    """PZMath.lerpFunc_EaseOutInQuad."""
    x = min(1.0, max(0.0, x))
    return 2 * x * x if x < 0.5 else 0.5 + (1 - (1 - (2 * x - 1)) ** 2) / 2


def slerp(a, b, t):
    d = sum(p * q for p, q in zip(a, b))
    if d < 0:
        b, d = tuple(-c for c in b), -d
    if d > 0.9995:
        v = [p + (q - p) * t for p, q in zip(a, b)]
    else:
        th = math.acos(d)
        s = math.sin(th)
        v = [p * math.sin((1 - t) * th) / s + q * math.sin(t * th) / s for p, q in zip(a, b)]
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def find_clip(folder, name):
    """Vanilla files mix .x and .X."""
    for ext in (".x", ".X"):
        path = os.path.join(folder, name + ext)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(os.path.join(folder, name + ".x"))


class Clip:
    def __init__(self, path, looped):
        xa = xanim.read(path)
        self.tracks = {t.bone: t for t in xa.tracks}
        self.end = max(max(t.R) if t.R else 0 for t in xa.tracks)
        self.tps = xa.ticks_per_second
        self.looped = looped

    def pose(self, bone, secs):
        tr = self.tracks.get(bone)
        if tr is None or not tr.R:
            return None
        t = secs * self.tps
        t = t % self.end if self.looped and self.end else min(t, self.end)
        return xanim.sample(tr, "R", t), xanim.sample(tr, "T", t)


def weights(t, t_raise, t_hold):
    """(looting, hold) node weights at time t."""
    w_raise = w_hold = 0.0
    if t >= t_raise:
        w_raise = ease((t - t_raise) / RAISE_BLEND_IN)
    if t >= t_hold:
        raw_at_hold = min(1.0, (t_hold - t_raise) / RAISE_BLEND_IN)
        w_raise = ease(raw_at_hold - (t - t_hold) / RAISE_BLEND_OUT)
        w_hold = ease((t - t_hold) / HOLD_BLEND_IN)
    return w_raise, w_hold


def build(kind, out, raise_seconds=0.5, hold_seconds=3.0):
    idle_name, weapon = KINDS[kind]
    idle = Clip(find_clip(BOB, idle_name), True)
    loot_path = find_clip(BOB, RAISE_CLIP)
    loot = Clip(loot_path, False)
    hold = Clip(find_clip(MOD_BOB, "Bob_TienInspect_%s_Hold" % kind), True)

    t_raise, t_hold = LEAD_IN, LEAD_IN + raise_seconds
    nframes = int(round((t_hold + hold_seconds) * FPS))
    bones = [t.bone for t in xanim.read(loot_path).tracks]
    tracks = {b: xanim.Track(b) for b in bones}
    phases = []
    for f in range(nframes + 1):
        t = f / float(FPS)
        w_raise, w_hold = weights(t, t_raise, t_hold)
        phases.append("%d %.3f %.3f" % (f, w_raise, w_hold))
        layers = [(w_hold, hold, t - t_hold), (w_raise, loot, (t - t_raise) * RAISE_SPEED), (1.0, idle, t)]
        for b in bones:
            remaining, total, rot, pos = 1.0, 0.0, None, [0.0, 0.0, 0.0]
            for w, clip, secs in layers:
                if w <= 0.001 or remaining <= 0.001:
                    continue
                p = clip.pose(b, secs)
                if p is None:
                    continue
                q, tr = p
                aw = min(w, remaining)
                remaining = max(0.0, remaining - w)
                if rot is None:
                    rot, total = q, aw
                else:
                    rot = slerp(rot, q, aw / (aw + total))
                    total += aw
                pos = [a + v * aw for a, v in zip(pos, tr)]
            if rot is not None:
                tick = f * TICKS_PER_FRAME
                tracks[b].R[tick], tracks[b].T[tick], tracks[b].S[tick] = rot, pos, [1.0, 1.0, 1.0]

    name = os.path.splitext(os.path.basename(out))[0]
    xanim.write_clip(loot_path, out, name, [tracks[b] for b in bones if tracks[b].R])
    with open(os.path.splitext(out)[0] + "_phases.txt", "w") as fh:
        fh.write("\n".join(phases) + "\n")
    print("[sequence] %s: %d frames, looting from frame %d, hold from frame %d; render with %s"
          % (out, nframes + 1, round(t_raise * FPS), round(t_hold * FPS), os.path.join(MEDIA, "models_X", weapon)))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in KINDS:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2],
          float(sys.argv[3]) if len(sys.argv) > 3 else 0.5,
          float(sys.argv[4]) if len(sys.argv) > 4 else 3.0)
