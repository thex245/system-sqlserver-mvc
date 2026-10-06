"""The cast: the Pasión specimen (an elongated, faceless mannequin that can grow a
smile) and the facility employee. Poses are in character space (faces -Y)."""
import bpy
import bmesh
from mathutils import Vector

import rig
from rig import v

CREATURE_SCALE = {"Neck": (0.8, 1.6, 0.8), "Spine": (0.86, 1.05, 0.86), "Spine1": (0.86, 1.05, 0.86),
                  "Spine2": (0.84, 1.05, 0.84), "Head": (0.92, 1.1, 0.92)}
for _s in ("Left", "Right"):
    CREATURE_SCALE.update({f"{_s}Arm": (0.8, 1.22, 0.8), f"{_s}ForeArm": (0.78, 1.3, 0.78),
                           f"{_s}Hand": (0.85, 1.2, 0.85), f"{_s}UpLeg": (0.82, 1.1, 0.82),
                           f"{_s}Leg": (0.78, 1.15, 0.78)})
    for _f in ("Index", "Middle", "Ring", "Pinky"):
        for _j in (1, 2, 3):
            CREATURE_SCALE[f"{_s}Hand{_f}{_j}"] = (0.8, 1.45, 0.8)

ARMS_DOWN = {"LeftArm": v(0.12, 0, -1), "LeftForeArm": v(0.05, -0.08, -1), "LeftHand": v(0.03, -0.05, -1),
             "RightArm": v(-0.12, 0, -1), "RightForeArm": v(-0.05, -0.08, -1), "RightHand": v(-0.03, -0.05, -1)}
STAND = dict(ARMS_DOWN, **{
    "LeftUpLeg": v(0.03, 0, -1), "LeftLeg": v(0, 0.02, -1), "RightUpLeg": v(-0.03, 0, -1), "RightLeg": v(0, 0.02, -1),
    "LeftFoot": v(0, -1, -0.4), "RightFoot": v(0, -1, -0.4),
    "Spine": v(0, 0, 1), "Spine1": v(0, 0, 1), "Spine2": v(0, 0, 1), "Neck": v(0, -0.1, 1), "look": v(0, -1, 0)})

SIT_HIPS = (0, 0, -0.88)
LEGS_SIT = {"LeftUpLeg": v(0.16, -0.75, 0.5), "LeftLeg": v(0, 0.3, -1), "RightUpLeg": v(-0.16, -0.75, 0.5),
            "RightLeg": v(0, 0.3, -1), "LeftFoot": v(0, -1, -0.2), "RightFoot": v(0, -1, -0.2)}
HUG_ARMS = {"LeftArm": v(0.25, -0.55, -0.4), "LeftForeArm": v(-0.75, -0.45, 0.1), "LeftHand": v(-0.8, -0.3, 0),
            "RightArm": v(-0.25, -0.55, -0.4), "RightForeArm": v(0.75, -0.45, 0.1), "RightHand": v(0.8, -0.3, 0)}
SIT_HUG = dict(LEGS_SIT, **HUG_ARMS, **{
    "Spine": v(0, -0.35, 1), "Spine1": v(0, -0.5, 1), "Spine2": v(0, -0.55, 1), "Neck": v(0, -0.9, 0.45),
    "look": v(0, -0.25, -1), "fingers": 0.5})


def sit_look(look, neck=(0, -0.45, 1)):
    return dict(LEGS_SIT, **HUG_ARMS, **{
        "Spine": v(0, -0.15, 1), "Spine1": v(0, -0.2, 1), "Spine2": v(0, -0.2, 1), "Neck": v(*neck),
        "look": v(*look), "fingers": 0.5})


def sit_reach(look, hand_dir):
    d = v(*hand_dir)
    p = sit_look(look)
    p.update({"RightArm": d, "RightForeArm": (d + v(0.03, 0, -0.02)).normalized(), "RightHand": d,
              "fingers": 0.08})
    return p


def skin_material():
    return rig.principled("pasion_skin", (0.80, 0.77, 0.73), rough=0.42, sss=0.25)


def make_creature(name="pasion"):
    c = rig.Character("Xbot.glb", name)
    c.proportions(CREATURE_SCALE)
    c.material(skin_material())
    c.surface = next(m for m in c.meshes if "Surface" in m.name)
    return c


def make_employee(name="employee", glb="Soldier.glb"):
    return rig.Character(glb, name, faces_neg_y=(glb != "Soldier.glb"))


def _crescent(bm, w, k, o, z0, y0, n=24):
    """Smile crescent in the XZ plane at depth y0. Returns (upper_edge, lower_edge) vertex lists."""
    up, lo = [], []
    for i in range(n + 1):
        x = -w + 2 * w * i / n
        t = (x / w) ** 2
        up.append(bm.verts.new((x, y0, z0 + k * t)))
        lo.append(bm.verts.new((x, y0, z0 + k * t - o * (1 - t))))
    for i in range(n):
        bm.faces.new((up[i], up[i + 1], lo[i + 1], lo[i]))
    return up, lo


def _smile_mesh(name, w, k, o, part):
    bm = bmesh.new()
    if part == "dark":
        _crescent(bm, w, k, o, 0.0, 0.0)
    else:
        import random
        rnd = random.Random(4)
        n = 24
        for sign in (1, -1):
            for i in range(n):
                x0 = -w * 0.9 + 2 * w * 0.9 * i / n
                x1 = x0 + 2 * w * 0.9 / n * rnd.uniform(0.6, 0.8)
                t = ((x0 + x1) / 2 / w) ** 2
                edge = k * t if sign > 0 else k * t - o * (1 - t)
                ln = rnd.uniform(0.006, 0.0095) * (1 - t * 0.7)
                a = bm.verts.new((x0, 0, edge))
                b = bm.verts.new((x1, 0, edge))
                cc = bm.verts.new((x1 * 0.9 + x0 * 0.1, 0, edge - sign * ln))
                d = bm.verts.new((x0 * 0.9 + x1 * 0.1, 0, edge - sign * ln))
                bm.faces.new((a, b, cc, d))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _face_probe(c, z):
    """Ray-cast the deformed head surface at height z: (front_y, half_width)."""
    dg = bpy.context.evaluated_depsgraph_get()
    head = c.joint("Head")
    sc = bpy.context.scene

    def hit(x):
        ok, loc, *_ = sc.ray_cast(dg, Vector((x, head.y - 1.0, z)), Vector((0, 1, 0)), distance=1.2)
        return loc if ok else None
    front = hit(head.x)
    hw = 0.0
    for i in range(1, 60):
        x = i * 0.0025
        if hit(head.x + x) is None or hit(head.x - x) is None:
            break
        hw = x
    return front.y, hw


def add_smile(c, rel_height=0.19, width_frac=0.88):
    """A dark crescent plus two rows of teeth on the blank face, driven by a shape key
    'smile' (0 = invisible slit, 1 = full grin). Every vertex of both shapes is
    ray-cast onto the face once (rest pose) and the result is parented rigidly to the
    Head bone, so nothing can slip at extreme head angles."""
    c.pose(STAND)
    head, top = c.joint("Head"), c.joint("HeadTop_End")
    z_mouth = head.z + (top.z - head.z) * rel_height
    front_y, half_w = _face_probe(c, z_mouth)
    width = half_w * width_frac
    origin = Vector((head.x, front_y, z_mouth))
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene

    def project(co, offset):
        w = origin + co
        ok, loc, *_ = sc.ray_cast(dg, Vector((w.x, w.y - 0.5, w.z)), Vector((0, 1, 0)), distance=0.6)
        if not ok:   # beyond the silhouette: tuck it behind the cheek
            return Vector((co.x, 0.03, co.z))
        return Vector((co.x, loc.y - offset - origin.y, co.z))

    mats = {"dark": rig.principled("mouth_dark", (0.004, 0.002, 0.002), rough=0.9, spec=0.1),
            "teeth": rig.principled("teeth", (0.72, 0.68, 0.58), rough=0.35)}
    c.mouth_parts, c.smile_keys = [], []
    parts = []
    for part, offset in (("dark", 0.0025), ("teeth", 0.0045)):
        me = _smile_mesh("smile_" + part, width, width * 0.55, width * 0.5, part)
        full = [vtx.co.copy() for vtx in me.vertices]
        slit = [Vector((p.x * 0.3, p.y, p.z * 0.02)) for p in full]
        wide = [Vector((p.x, p.y, p.z * 0.16 + 0.35 * width * 0.5 * (p.x / width) ** 2)) for p in full]
        parts.append((part, me, [project(p, offset) for p in full], [project(p, offset) for p in slit],
                      [project(p, offset) for p in wide]))
    for part, me, full, slit, wide in parts:
        me.materials.append(mats[part])
        for vtx, p in zip(me.vertices, slit):
            vtx.co = p
        ob = bpy.data.objects.new("smile_" + part, me)
        sc.collection.objects.link(ob)
        ob.location = origin
        ob.shape_key_add(name="Basis")
        skw = ob.shape_key_add(name="wide", from_mix=False)
        for i, p in enumerate(wide):
            skw.data[i].co = p
        sk = ob.shape_key_add(name="smile", from_mix=False)
        for i, p in enumerate(full):
            sk.data[i].co = p
        bpy.context.view_layer.update()
        mw = ob.matrix_world.copy()
        ob.parent = c.arm
        ob.parent_type = "BONE"
        ob.parent_bone = rig.P + "Head"
        bpy.context.view_layer.update()
        ob.matrix_world = mw
        sk.value = skw.value = 0.0
        c.mouth_parts.append(ob)
        c.smile_keys.append((skw, sk))
    c.rest_reset()


def set_smile(c, value):
    """0 = closed, 0.5 = a thin line stretched across the face, 1 = full grin."""
    wide = min(1.0, value / 0.5) if value <= 0.5 else 1.0 - (value - 0.5) / 0.5
    full = 0.0 if value <= 0.5 else (value - 0.5) / 0.5
    for skw, sk in c.smile_keys:
        skw.value, sk.value = wide, full


def key_smile(c, frame, value):
    """Keyframe the smile. Put keys on 0 / 0.5 / 1 so the two stages interpolate cleanly."""
    set_smile(c, value)
    for skw, sk in c.smile_keys:
        skw.keyframe_insert("value", frame=frame)
        sk.keyframe_insert("value", frame=frame)
