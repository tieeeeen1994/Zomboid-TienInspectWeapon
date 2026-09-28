"""
Read and write Project Zomboid's text DirectX (.x) animation files.

Plain Python with no dependencies, so it runs both under the system python3 and inside
Blender (x_import.py and x_export.py import it from this folder).

Why .x and not FBX. The game loads every animation through Assimp
(zombie/core/skinnedmodel/model/FileTask_LoadAnimation), but it treats the formats
differently: an .x clip is used exactly as it is in the file, while an .fbx or .glb clip
gets its bone positions scaled by 0.01 and a -90 degree X rotation worked into its root
bones (ProcessedAiSceneParams.animBonesScaleModifier / animBonesRotateModifier). Writing
.x files the way vanilla's are written means none of that conversion can go wrong.

What a file has to contain. ProcessedAiScene only builds clips from a scene that has a
mesh with bones: with no skinned mesh it logs "No such mesh" and the file yields nothing.
That is why every vanilla clip carries the whole Bob body mesh. write_clip() therefore
keeps everything of a vanilla source file before its AnimTicksPerSecond (templates,
material, the frame hierarchy and the skinned mesh) and replaces only the AnimationSet.

Conventions, checked against the vanilla files (see check_conventions below):
- FrameTransformMatrix is 16 floats, row-major with the translation in the last row
  (row-vector convention, v' = v * M). to_colmajor() turns it into the usual
  column-vector 4x4 (translation in the last column), which is what Blender uses.
- AnimationKey 0 (R) stores a quaternion as w, x, y, z; key 1 (S) and key 2 (T) are
  3 floats. The stored quaternion is the *conjugate* of the rotation the frame matrix
  describes (Assimp's XFileParser reads it as (w, -x, -y, -z)).
- AnimTicksPerSecond is 4800 in vanilla (160 ticks per frame at 30 fps).
- The clip's name in game is the AnimationSet's name (ImportedSkeleton.processAnimation,
  text after a '|' if there is one), not the file name. Keep them the same.
"""

import math
import re

TOKEN = re.compile(r'"[^"]*"|[A-Za-z_][A-Za-z0-9_\-.]*|-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?|[{};,]|\S')


class Block:
    def __init__(self, kind, name=None):
        self.kind = kind
        self.name = name
        self.data = []      # number and string tokens, in order
        self.children = []  # nested blocks
        self.refs = []      # { Name } references

    def numbers(self):
        return [float(t) for t in self.data if not t.startswith('"')]

    def child(self, kind):
        for c in self.children:
            if c.kind == kind:
                return c
        return None


def _tokens(text):
    return [t for t in TOKEN.findall(text) if t not in (";", ",")]


def _parse_body(tokens, i, block):
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if t == "}":
            return i + 1
        if t == "{":
            block.refs.append(tokens[i + 1])
            i += 3
            continue
        is_ident = t[0].isalpha() or t[0] == "_"
        if is_ident and i + 1 < n and tokens[i + 1] == "{":
            sub = Block(t)
            i = _parse_body(tokens, i + 2, sub)
            block.children.append(sub)
            continue
        if is_ident and i + 2 < n and tokens[i + 2] == "{" and (tokens[i + 1][0].isalpha() or tokens[i + 1][0] == "_"):
            sub = Block(t, tokens[i + 1])
            i = _parse_body(tokens, i + 3, sub)
            block.children.append(sub)
            continue
        block.data.append(t)
        i += 1
    return i


def parse(text):
    """The whole file as a Block tree (templates dropped)."""
    body = text[text.index("\n"):]  # skip the "xof 0303txt 0032" header
    body = re.sub(r"template\s+\w+\s*\{[^}]*\}", "", body)
    root = Block("root")
    _parse_body(_tokens(body), 0, root)
    return root


# ---------------------------------------------------------------- matrices


def to_colmajor(m16):
    """Row-major row-vector .x matrix -> column-vector 4x4 (list of rows)."""
    return [[m16[c * 4 + r] for c in range(4)] for r in range(4)]


def quat_to_mat3(w, x, y, z):
    """Column-vector rotation matrix of a unit quaternion."""
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ]


def mat3_to_quat(m):
    """Unit quaternion (w, x, y, z) of a column-vector rotation matrix."""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        return ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        return ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
    return ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)


def srt_to_mat4(s, q_file, t):
    """A key's scale, file quaternion and translation -> column-vector local 4x4."""
    w, x, y, z = q_file
    r = quat_to_mat3(w, -x, -y, -z)  # the file stores the conjugate
    return [
        [r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t[0]],
        [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t[1]],
        [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def mat4_to_srt(m):
    """Column-vector local 4x4 -> (scale, file quaternion, translation)."""
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    s = [math.sqrt(sum(v * v for v in col)) for col in cols]
    r = [[m[i][j] / s[j] for j in range(3)] for i in range(3)]
    w, x, y, z = mat3_to_quat(r)
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    return s, (w, -x, -y, -z), [m[0][3], m[1][3], m[2][3]]


# ---------------------------------------------------------------- reading


class Frame:
    def __init__(self, name, parent, matrix):
        self.name = name
        self.parent = parent  # name or None
        self.matrix = matrix  # column-vector 4x4, relative to parent


class Track:
    """One bone's keys: {time_ticks: value}; value is a list (S, T) or a (w,x,y,z) file quaternion (R)."""

    def __init__(self, bone):
        self.bone = bone
        self.S = {}
        self.R = {}
        self.T = {}


class XAnim:
    def __init__(self):
        self.frames = []        # Frame, parents before children
        self.ticks_per_second = 4800
        self.clip_name = None
        self.tracks = []        # Track, in file order
        self.mesh = None        # (vertices, faces, skin) or None
        self.text = ""          # the source text

    def frame(self, name):
        for f in self.frames:
            if f.name == name:
                return f
        return None


def _collect_frames(block, parent, out):
    for c in block.children:
        if c.kind != "Frame":
            continue
        ftm = c.child("FrameTransformMatrix")
        m = to_colmajor(ftm.numbers()) if ftm else [[1.0 if r == k else 0.0 for k in range(4)] for r in range(4)]
        out.append(Frame(c.name, parent, m))
        _collect_frames(c, c.name, out)


def _read_mesh(block):
    nums = block.numbers()
    nv = int(nums[0])
    verts = [tuple(nums[1 + i * 3:4 + i * 3]) for i in range(nv)]
    k = 1 + nv * 3
    nf = int(nums[k])
    k += 1
    faces = []
    for _ in range(nf):
        c = int(nums[k])
        faces.append(tuple(int(v) for v in nums[k + 1:k + 1 + c]))
        k += 1 + c
    skin = {}
    for c in block.children:
        if c.kind != "SkinWeights":
            continue
        name = c.data[0].strip('"')
        vals = c.numbers()
        n = int(vals[0])
        skin[name] = (
            [int(v) for v in vals[1:1 + n]],
            vals[1 + n:1 + 2 * n],
            to_colmajor(vals[1 + 2 * n:17 + 2 * n]),
        )
    return verts, faces, skin


def read(path, with_mesh=False):
    with open(path, "r", encoding="latin-1") as fh:
        text = fh.read()
    root = parse(text)
    xa = XAnim()
    xa.text = text
    _collect_frames(root, None, xa.frames)
    tps = root.child("AnimTicksPerSecond")
    if tps:
        xa.ticks_per_second = int(tps.numbers()[0])
    aset = root.child("AnimationSet")
    if aset:
        xa.clip_name = aset.name
        for anim in aset.children:
            if anim.kind != "Animation" or not anim.refs:
                continue
            tr = Track(anim.refs[0])
            for key in anim.children:
                if key.kind != "AnimationKey":
                    continue
                nums = key.numbers()
                ktype, nkeys = int(nums[0]), int(nums[1])
                k = 2
                for _ in range(nkeys):
                    t, cnt = int(nums[k]), int(nums[k + 1])
                    v = nums[k + 2:k + 2 + cnt]
                    k += 2 + cnt
                    if ktype == 0:
                        tr.R[t] = tuple(v)
                    elif ktype == 1:
                        tr.S[t] = list(v)
                    elif ktype == 2:
                        tr.T[t] = list(v)
            xa.tracks.append(tr)
    if with_mesh:
        for f in root.children:
            if f.kind == "Frame":
                mesh = f.child("Mesh")
                if mesh:
                    xa.mesh = _read_mesh(mesh)
                    break
    return xa


def sample(track, key, t):
    """A track's value at tick t: linear for S/T, nlerp for R, held past the ends."""
    keys = getattr(track, key)
    if not keys:
        return None
    times = sorted(keys)
    if t <= times[0]:
        return keys[times[0]]
    if t >= times[-1]:
        return keys[times[-1]]
    for a, b in zip(times, times[1:]):
        if a <= t <= b:
            f = (t - a) / float(b - a)
            va, vb = keys[a], keys[b]
            if key == "R":
                dot = sum(p * q for p, q in zip(va, vb))
                sign = -1.0 if dot < 0 else 1.0
                v = [p + (q * sign - p) * f for p, q in zip(va, vb)]
                n = math.sqrt(sum(c * c for c in v))
                return tuple(c / n for c in v)
            return [p + (q - p) * f for p, q in zip(va, vb)]
    return keys[times[-1]]


# ---------------------------------------------------------------- writing


def _fmt(v):
    s = "%.6f" % v
    return "0.000000" if s == "-0.000000" else s


def reduce_keys(keys, eps=1e-6):
    """Drop keys that sit in a run of identical values (first and last always kept),
    as vanilla does: a bone that never moves ends up with two keys."""
    times = sorted(keys)
    if len(times) <= 2:
        return dict(keys)
    same = lambda a, b: max(abs(p - q) for p, q in zip(keys[a], keys[b])) <= eps
    out = {times[0]: keys[times[0]]}
    for prev, t, nxt in zip(times, times[1:], times[2:]):
        if not (same(prev, t) and same(t, nxt)):
            out[t] = keys[t]
    out[times[-1]] = keys[times[-1]]
    return out


def _key_block(letter, ktype, keys):
    keys = reduce_keys(keys)
    lines = ["  AnimationKey %s {" % letter, "   %d;" % ktype, "   %d;" % len(keys)]
    times = sorted(keys)
    for i, t in enumerate(times):
        v = keys[t]
        end = ";;;" if i == len(times) - 1 else ";;,"
        lines.append("   %d;%d;%s%s" % (t, len(v), ",".join(_fmt(c) for c in v), end))
    lines.append("  }")
    return lines


def write_clip(template_path, out_path, clip_name, tracks, ticks_per_second=4800):
    """Write tracks as a new clip, reusing everything else of a vanilla .x file."""
    with open(template_path, "r", encoding="latin-1") as fh:
        text = fh.read()
    # The data block, not "template AnimTicksPerSecond" in the header
    m = re.search(r"^AnimTicksPerSecond\b", text, re.M) or re.search(r"^AnimationSet\b", text, re.M)
    head = text[:m.start()]
    out = [head.rstrip("\n"), "", "AnimTicksPerSecond  {", " %d;" % ticks_per_second, "}", "",
           "AnimationSet %s {" % clip_name, " "]
    for tr in tracks:
        out += ["", " Animation {", "  ", "  { %s }" % tr.bone, ""]
        out += _key_block("S", 1, tr.S) + [""]
        out += _key_block("R", 0, tr.R) + [""]
        out += _key_block("T", 2, tr.T)
        out.append(" }")
    out.append("}")
    with open(out_path, "w", encoding="latin-1", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- self-check


def check_conventions(path):
    """Largest difference between each bone's frame-0 key and its FrameTransformMatrix.

    Vanilla writes the bind pose as the first key of bones that do not move in a clip,
    so a small number here confirms the matrix layout and the conjugated quaternion.
    """
    xa = read(path)
    worst = []
    for tr in xa.tracks:
        f = xa.frame(tr.bone)
        if not f or 0 not in tr.R:
            continue
        m = srt_to_mat4(tr.S.get(0, [1, 1, 1]), tr.R[0], tr.T.get(0, [0, 0, 0]))
        d = max(abs(m[r][c] - f.matrix[r][c]) for r in range(4) for c in range(4))
        worst.append((d, tr.bone))
    return sorted(worst, reverse=True)


def validate(path):
    """Problems that would make the game reject or misplay a clip; [] when it is fine."""
    xa = read(path, with_mesh=True)
    problems = []
    names = {f.name for f in xa.frames}
    if "Dummy01" not in names:
        problems.append("no Dummy01 frame (the game finds the skeleton by it)")
    if not xa.mesh or not xa.mesh[2]:
        problems.append("no skinned mesh (the game loads no clip from a file without one)")
    if not xa.clip_name:
        problems.append("no AnimationSet")
    for tr in xa.tracks:
        if tr.bone not in names:
            problems.append("track for unknown bone %s" % tr.bone)
        for key in ("S", "R", "T"):
            if not getattr(tr, key):
                problems.append("%s has no %s keys" % (tr.bone, key))
    return problems


def compare(path_a, path_b):
    """Largest local-matrix difference between two clips, sampled every 160 ticks."""
    a, b = read(path_a), read(path_b)
    ta, tb = {t.bone: t for t in a.tracks}, {t.bone: t for t in b.tracks}
    end = max(max(t.R) for t in a.tracks)
    worst = (0.0, None, None)
    for bone in ta:
        if bone not in tb:
            return (float("inf"), bone, "missing")
        for tick in range(0, end + 1, 160):
            ma, mb = (srt_to_mat4(sample(t[bone], "S", tick) or [1, 1, 1], sample(t[bone], "R", tick),
                                  sample(t[bone], "T", tick)) for t in (ta, tb))
            d = max(abs(ma[r][c] - mb[r][c]) for r in range(4) for c in range(4))
            if d > worst[0]:
                worst = (d, bone, tick)
    return worst


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "compare":
        print("worst local matrix difference: %.2e (%s, tick %s)" % compare(sys.argv[2], sys.argv[3]))
        sys.exit(0)
    for p in sys.argv[1:]:
        problems = validate(p)
        res = check_conventions(p)
        print(p.rsplit("/", 1)[-1], "OK" if not problems else "PROBLEMS", "- bones:", len(res),
              "frame-0 vs frame matrix:", "%.6f %s" % res[0] if res else "-")
        for msg in problems:
            print("   ", msg)
