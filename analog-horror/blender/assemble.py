"""Assemble the film scene: set + cast (NLA-composited mocap) + performance layers + props + camera.

blender -b set.blend --python assemble.py -- OUT.blend
"""
import json, math, os, sys
import numpy as np
import bpy
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import setlib as S
import animkit as K
import anim
from layout import *        # noqa: F401,F403
from timeline import *      # noqa: F401,F403
from cast import CAST, BY_TAG, WAITER, WALK_SPEED

OUT = sys.argv[sys.argv.index("--") + 1]
CHAR_DIR = os.environ.get("VAMA_CHARS", r"D:\VAMA_work\blend\chars")
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, frame(FILM_END)
CH = S.coll("characters")
NF = frame(FILM_END) + 2
TT = (np.arange(1, NF + 1) - 1) / FPS          # film time of frame i+1
FRAMES = np.arange(1, NF + 1, dtype=np.float32)
EMPTY_T0 = SEG["empty"][1]

# Biped hierarchy: the thighs hang off "Bip01 Spine" (not the pelvis), so an upper-body overlay must
# leave that bone alone too or it drags the legs with it.
UPPER_EXCLUDE = ("Bip01 Pelvis", "Bip01 Spine", "Bip01 L Thigh", "Bip01 L Calf", "Bip01 L Foot", "Bip01 L Toe0",
                 "Bip01 R Thigh", "Bip01 R Calf", "Bip01 R Foot", "Bip01 R Toe0")


# ------------------------------------------------------------------------------------ cast
def load_char(tag):
    path = os.path.join(CHAR_DIR, tag + ".blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in (f"{tag}_rig", f"{tag}_body")]
        dst.actions = [n for n in src.actions if n.startswith(tag + ":")]
    arm, mesh = bpy.data.objects[f"{tag}_rig"], bpy.data.objects[f"{tag}_body"]
    for o in (arm, mesh):
        CH.objects.link(o)
    return arm, mesh


def make_root(tag):
    r = bpy.data.objects.new(f"{tag}_root", None)
    r.empty_display_size = 0.3
    CH.objects.link(r)
    return r


def upper_body(act):
    cp = act.copy()
    cp.name = act.name + "|upper"
    for layer in getattr(cp, "layers", []):
        for st in layer.strips:
            for cb in st.channelbags:
                for fc in list(cb.fcurves):
                    if any(f'"{b}"' in fc.data_path for b in UPPER_EXCLUDE):
                        cb.fcurves.remove(fc)
    if hasattr(cp, "fcurves"):
        for fc in list(cp.fcurves):
            if any(f'"{b}"' in fc.data_path for b in UPPER_EXCLUDE):
                cp.fcurves.remove(fc)
    return cp


def new_strip(track, name, start_t, act, a0, a1):
    st = track.strips.new(name, int(round(K.fr(start_t))), act)
    if hasattr(st, "action_slot") and st.action_slot is None and len(act.slots):
        st.action_slot = act.slots[0]
    st.action_frame_start = a0
    st.action_frame_end = a1
    st.use_auto_blend = False
    st.extrapolation = "NOTHING"
    return st


def quat_fcurves(act):
    out = {}
    for fc in anim._fcurves(act):
        if fc.data_path.endswith("rotation_quaternion"):
            out.setdefault(fc.data_path, {})[fc.array_index] = fc
    return out


def align_blend(prev_act, prev_frame, act, frame, tag):
    """If a bone's rotation in `act` (at its blend start) sits in the opposite quaternion hemisphere of
    the clip it crossfades from, NLA blending would swing that limb the long way round. Return a copy
    of `act` with those bones' channels negated (same rotations, matching hemisphere)."""
    qa, qb = quat_fcurves(prev_act), quat_fcurves(act)
    bad = []
    for path, cb in qb.items():
        ca = qa.get(path)
        if not ca or len(ca) != 4 or len(cb) != 4:
            continue
        a = np.array([ca[i].evaluate(prev_frame) for i in range(4)])
        b = np.array([cb[i].evaluate(frame) for i in range(4)])
        if np.dot(a, b) < 0:
            bad.append(path)
    if not bad:
        return act
    cp = act.copy()
    cp.name = act.name + "|aligned"
    for path, ch in quat_fcurves(cp).items():
        if path in bad:
            for fc in ch.values():
                co = np.empty(len(fc.keyframe_points) * 2)
                fc.keyframe_points.foreach_get("co", co)
                co[1::2] *= -1
                fc.keyframe_points.foreach_set("co", co)
                fc.update()
    print(f"NLA {tag}: {len(bad)} bone(s) re-aligned for blend into {act.name}", flush=True)
    return cp


def build_nla(arm, tag, strips):
    ad = arm.animation_data_create()
    ad.action = None
    base = [ad.nla_tracks.new(), ad.nla_tracks.new()]
    base[0].name, base[1].name = "base_A", "base_B"
    over = None
    base_strips = [s for s in strips if not s.get("overlay")]
    k = 0
    made = []
    prev = None          # (action, action_frame_start, strip_start_time) of the clip underneath
    for s in strips:
        act = bpy.data.actions[f"{tag}:{s['clip']}"]
        if s.get("upper"):
            act = upper_body(act)
        lo = act.get("lo", 1)
        a0 = s["offset"] - lo + 1
        a1 = a0 + (s["t1"] - s["t0"]) * FPS
        if prev is not None:
            pact, pa0, pt0 = prev
            act = align_blend(pact, pa0 + (s["t0"] - pt0) * FPS, act, a0, tag)
        if not s.get("overlay"):
            prev = (act, a0, s["t0"])
        if s.get("overlay"):
            if over is None:
                over = ad.nla_tracks.new()
                over.name = "overlay"
            st = new_strip(over, s["clip"], s["t0"], act, a0, a1)
            st.blend_in = st.blend_out = s["blend"] * FPS
            continue
        tr = base[k % 2]
        st = new_strip(tr, s["clip"], s["t0"], act, a0, a1)
        if k % 2 == 1:
            st.blend_in = s["blend"] * FPS
            nxt = base_strips[k + 1]["blend"] if k + 1 < len(base_strips) else 0.0
            st.blend_out = nxt * FPS
        made.append(st)
        k += 1
    made[0].extrapolation = "HOLD"
    made[-1].extrapolation = "HOLD_FORWARD"
    return ad


def mesh_points(mesh):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg)
    me = ev.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def seat_fix(c, arm, mesh, root, seat_h, times):
    """Lift/lower the character so the buttocks rest on the seat; returns (dz, lowest_shoe_z_after).
    Sampled over several moments of the film (the feet move with the mocap)."""
    dzs, feet = [], []
    for t in times:
        sc.frame_set(int(K.fr(t)))
        pel = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
        P = mesh_points(mesh)
        d = np.hypot(P[:, 0] - pel.x, P[:, 1] - pel.y)
        butt = P[(d < 0.15) & (P[:, 2] < pel.z)][:, 2].min()
        dzs.append(seat_h - 0.012 - butt)          # sink ~1 cm into the cushion
        feet.append(P[:, 2].min())
    dz = float(np.median(dzs))
    return dz, min(feet) + dz


chars = {}
ONLY = set(os.environ.get("VAMA_ONLY", "").split(",")) - {""}     # review builds: subset of the cast
CAST_USED = [c for c in CAST if not ONLY or c["tag"] in ONLY]
for c in CAST_USED:
    arm, mesh = load_char(c["tag"])
    root = make_root(c["tag"])
    arm.parent = root
    arm.matrix_parent_inverse = Matrix.Identity(4)
    arm.matrix_basis = anim.rest_matrix(arm)
    chars[c["tag"]] = (arm, mesh, root)
    if c["tag"] == "waiter":
        continue
    root.location = (c["pelvis"][0], c["pelvis"][1], 0.0)
    root.rotation_euler = (0, 0, c["yaw"])
    build_nla(arm, c["tag"], c["strips"])

# Diners whose knees hit a table apron sit a little further back (chair moves with them).
_dp = os.environ.get("VAMA_DINER_OFFSETS", r"D:\VAMA_work\blend\diner_offsets.json")
DINER_BACK = json.load(open(_dp)) if os.path.exists(_dp) else {}
for tag, back in DINER_BACK.items():
    c = BY_TAG.get(tag) if tag in chars else None
    if not c or tag in ("man", "woman"):
        continue
    fwd = Vector((math.sin(c["yaw"]), -math.cos(c["yaw"]), 0))
    chars[tag][2].location -= fwd * back
    for o in bpy.data.objects:
        if o.type == "EMPTY" and o.name.endswith(f"_chair_{tag}"):
            o.location -= fwd * back
    print(f"DINER {tag} moved back {back * 100:.1f} cm", flush=True)
_cp = os.environ.get("VAMA_CHAIR_OFFSETS", r"D:\VAMA_work\blend\chair_offsets.json")
CHAIR_BACK = json.load(open(_cp)) if os.path.exists(_cp) else {}
for tag, back in CHAIR_BACK.items():
    c = BY_TAG.get(tag) if tag in chars else None
    if not c:
        continue
    fwd = Vector((math.sin(c["yaw"]), -math.cos(c["yaw"]), 0))
    for o in bpy.data.objects:
        if o.type == "EMPTY" and (o.name.endswith(f"_chair_{tag}") or o.name == f"chair_{tag}"):
            o.location -= fwd * back
            print(f"CHAIR {o.name} slid back {back * 100:.1f} cm", flush=True)

# Hero meshes get a render-time subdivision for the long-lens close-ups.
for tag in ("man", "woman"):
    mesh = chars[tag][1]
    sub = mesh.modifiers.new("subd", "SUBSURF")
    sub.levels, sub.render_levels = 0, 1

# Seat heights for seated characters (chairs 0.455, booths 0.45), measured on the real pose.
SEATED = [c for c in CAST_USED if c["tag"] not in ("waiter", "bar", "chef")]
seat_dz = {}
for c in SEATED:
    arm, mesh, root = chars[c["tag"]]
    h = 0.45 if c["tag"].startswith("b") else 0.455
    t_samples = list(np.arange(3.0, 78.0 if c["tag"] == "man" else 115.0, 3.0))
    dz, feet = seat_fix(c, arm, mesh, root, h, t_samples)
    if feet < -0.01:                      # never let shoes sink into the floor
        dz += -0.01 - feet
        feet = -0.01
    seat_dz[c["tag"]] = dz
    root.location.z = dz
    print(f"SEAT {c['tag']:7s} dz={dz:+.3f} feet_after={feet:+.3f}")

# ------------------------------------------------------------------------------------ table heights
# The mocap was recorded at a slightly lower table: each table is lowered by what the contact QA
# measured (hands/forearms sinking into it), moving top, cloth and the whole table setting together.
TABLE_DZ = {}
_tp = os.environ.get("VAMA_TABLE_OFFSETS", r"D:\VAMA_work\blend\table_offsets.json")
if os.path.exists(_tp):
    TABLE_DZ = json.load(open(_tp))
for tname, dz in TABLE_DZ.items():
    if abs(dz) < 1e-4:
        continue
    if tname.startswith("booth"):
        k = tname[-1]
        pre = [f"booth{k}_table", f"booth{k}_votive", f"booth{k}_wax", f"booth{k}_flame", f"booth{k}_light"]
        pre += [f"booth_{d['tag']}_" for d in BOOTH_DINERS if d["tag"].startswith(f"b{k}")]
        for o in bpy.data.objects:
            if o.name.startswith(tuple(pre)):
                o.location.z += dz
        continue
    root = bpy.data.objects.get(f"{tname}_table")
    top0 = COUPLE_TABLE_TOP if tname == "couple" else next(
        (0.746 if t["kind"] == "round" else 0.75) for t in OTHER_TABLES if t["name"] == tname)
    if root:
        root.scale.z *= (top0 + dz) / top0
    for o in bpy.data.objects:
        if o.name.startswith((f"{tname}_cloth", f"{tname}_d", f"{tname}_votive", f"{tname}_wax", f"{tname}_flame",
                              f"{tname}_light")) or (tname == "couple" and o.name == "couple_bottle"):
            o.location.z += dz
    print(f"TABLE {tname} lowered {dz * 100:+.1f} cm", flush=True)
COUPLE_TOP_EFF = COUPLE_TABLE_TOP + TABLE_DZ.get("couple", 0.0)

# ------------------------------------------------------------------------------------ man / woman root changes
MAN_ARM, MAN_MESH, MAN_ROOT = chars["man"]
W_ARM, W_MESH, W_ROOT = chars["woman"]
T_STAND = SEG["standing"][1]
for f, pos, yaw, z in ((1, MAN_SEAT, MAN_YAW, seat_dz["man"]), (K.fr(T_STAND), MAN_STAND3, MAN_STAND3_YAW, 0.0),
                       (K.fr(SEG["ring"][1]), MAN_STAND, MAN_STAND_YAW, 0.0)):
    MAN_ROOT.location = (pos[0], pos[1], z)
    MAN_ROOT.rotation_euler = (0, 0, yaw)
    MAN_ROOT.keyframe_insert("location", frame=f)
    MAN_ROOT.keyframe_insert("rotation_euler", frame=f)
for fc in K._fcurves(MAN_ROOT.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "CONSTANT"
# The standing "talk angry" mocap slowly turns the whole body ~49 deg away from her; counter-rotate
# 75 % of that drift at the root so he keeps confronting her while all gestures stay intact.
yaws, ts = [], []
for f in range(int(K.fr(T_STAND + 0.1)), int(K.fr(SEG["ring"][1])), 5):
    sc.frame_set(f)
    m = MAN_ARM.matrix_world @ MAN_ARM.pose.bones["Bip01 Pelvis"].matrix
    fwd = Vector(m.col[1][:3])
    yaws.append(math.atan2(fwd.y, fwd.x))
    ts.append(f)
yaws = np.unwrap(np.array(yaws))
for f, y in zip(ts, yaws):
    MAN_ROOT.rotation_euler = (0, 0, MAN_STAND3_YAW - 0.75 * (y - yaws[0]))
    MAN_ROOT.keyframe_insert("rotation_euler", index=2, frame=f)
MAN_ROOT.rotation_euler = (0, 0, MAN_STAND_YAW)          # the ring segment starts on a cut
MAN_ROOT.keyframe_insert("rotation_euler", index=2, frame=K.fr(SEG["ring"][1]))
for fc in K._fcurves(MAN_ROOT.animation_data.action):
    if fc.data_path == "rotation_euler" and fc.array_index == 2:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR" if ts[0] <= kp.co.x < ts[-1] else "CONSTANT"
print(f"ROOT man drift compensated: {math.degrees(yaws[-1] - yaws[0]):.1f} deg", flush=True)
T_APPEAR = BEATS["she_appears"]
for i, (pos, yaw) in enumerate([(WOMAN_SEAT, WOMAN_YAW), (WOMAN_FINAL_SEAT, WOMAN_FINAL_YAW)]):
    W_ROOT.rotation_euler = (0, 0, yaw)
    W_ROOT.location = (pos[0], pos[1], W_ROOT.location.z)
    W_ROOT.keyframe_insert("rotation_euler", frame=1 if i == 0 else K.fr(EMPTY_T0))
    W_ROOT.keyframe_insert("location", frame=1 if i == 0 else K.fr(EMPTY_T0))
for fc in K._fcurves(W_ROOT.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "CONSTANT"

# ------------------------------------------------------------------------------------ waiter walks
if "waiter" in chars:
    WA, WM, WR = chars["waiter"]
    wad = WA.animation_data_create()
    wtr = wad.nla_tracks.new()
    walk = bpy.data.actions["waiter:walk"]
    for w in WAITER["walks"]:
        n = (w["t1"] - w["t0"]) * FPS
        st = new_strip(wtr, "walk", w["t0"], walk, 1, 1 + n)
        st.extrapolation = "NOTHING"
        for f, (x, y) in ((K.fr(w["t0"]) - 1, w["start"]), (K.fr(w["t0"]), w["start"])):
            WR.location = (x, y, 0.0)
            WR.rotation_euler = (0, 0, w["yaw"])
            WR.keyframe_insert("location", frame=f)
            WR.keyframe_insert("rotation_euler", frame=f)
    for fc in K._fcurves(WR.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"

# ------------------------------------------------------------------------------------ visibility
for tag, (arm, mesh, root) in chars.items():
    if tag == "waiter":
        iv = [(w["t0"], w["t1"]) for w in WAITER["walks"]]
    elif tag == "woman":
        iv = [(0.0, EMPTY_T0), (T_APPEAR, FILM_END + 1)]
    else:
        iv = [(0.0, EMPTY_T0)]
    K.visibility(mesh, iv, NF)

if os.environ.get("VAMA_STAGE", "full") != "cast":
    exec(open(os.path.join(HERE, "assemble_perf.py"), encoding="utf-8").read())
    exec(open(os.path.join(HERE, "assemble_props.py"), encoding="utf-8").read())
    exec(open(os.path.join(HERE, "assemble_camera.py"), encoding="utf-8").read())
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print("SAVED", OUT)
