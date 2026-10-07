"""Contact / interpenetration QA over the whole film (no rendering).

blender -b film.blend --python qa_contacts.py -- OUT.json [step]
Measures, per character and sampled frame: hands/forearms sinking into the table top, knees/thighs
hitting the table underside, back going through the chair backrest, feet below the floor, and the
standing man's hands vs the table. Writes worst cases per character.
"""
import json, math, os, sys
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from layout import *        # noqa
from timeline import SEG, FREEZE_AT, FPS
from cast import CAST

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
STEP = int(args[1]) if len(args) > 1 else 10
sc = bpy.context.scene

_tp = os.environ.get("VAMA_TABLE_OFFSETS", r"D:\VAMA_work\blend\table_offsets.json")
DZ = json.load(open(_tp)) if os.path.exists(_tp) else {}
TABLES = [dict(kind="round", c=COUPLE_TABLE, r=COUPLE_R, top=COUPLE_TABLE_TOP + DZ.get("couple", 0.0))]
for t in OTHER_TABLES:
    if t["kind"] == "round":
        TABLES.append(dict(kind="round", c=t["center"], r=0.398, top=0.746 + DZ.get(t["name"], 0.0)))
    else:
        TABLES.append(dict(kind="rect", c=t["center"], h=(0.567, 0.353), top=0.75 + DZ.get(t["name"], 0.0)))
for k, by in enumerate(BOOTHS):
    TABLES.append(dict(kind="rect", c=(0.45, by, 0), h=(0.4, 0.35), top=0.76 + DZ.get(f"booth{k}", 0.0)))


def inside(t, xy, margin=0.0):
    dx, dy = xy[:, 0] - t["c"][0], xy[:, 1] - t["c"][1]
    if t["kind"] == "round":
        return np.hypot(dx, dy) < t["r"] - margin
    return (np.abs(dx) < t["h"][0] - margin) & (np.abs(dy) < t["h"][1] - margin)


def nearest_table(xy):
    return min(TABLES, key=lambda t: math.hypot(xy[0] - t["c"][0], xy[1] - t["c"][1]))


GROUPS = {
    "hands": ["Hand", "Finger"],
    "forearm": ["Forearm"],
    "legs": ["Thigh", "Calf"],
    "back": ["Spine", "Spine1", "Spine2", "Neck"],
    "feet": ["Foot", "Toe0"],
}


def group_masks(mesh):
    """Vertex index masks by dominant bone group."""
    me = mesh.data
    names = {vg.index: vg.name for vg in mesh.vertex_groups}
    dom = np.full(len(me.vertices), "", dtype=object)
    for v in me.vertices:
        if v.groups:
            g = max(v.groups, key=lambda g: g.weight)
            dom[v.index] = names.get(g.group, "")
    def cls(n):
        if not n.startswith("Bip01"):
            return ""
        if "Finger" in n or n.endswith(" Hand"):
            return "hands"
        if n.endswith("Forearm"):
            return "forearm"
        if n.endswith("Thigh") or n.endswith("Calf"):
            return "legs"
        if n in ("Bip01 Spine", "Bip01 Spine1", "Bip01 Spine2", "Bip01 Neck"):
            return "back"
        if n.endswith("Foot") or n.endswith("Toe0"):
            return "feet"
        return ""
    c = np.array([cls(n) for n in dom])
    return {k: c == k for k in GROUPS}


def points(mesh):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg)
    me = ev.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


chars = []
for c in CAST:
    mesh = bpy.data.objects.get(f"{c['tag']}_body")
    if mesh is None or c["tag"] in ("waiter", "chef", "bar"):
        continue
    chars.append((c, mesh, group_masks(mesh)))

chairs = {}
for o in bpy.data.objects:
    if o.type == "EMPTY" and ("chair" in o.name) and not o.name.startswith("barstool"):
        chairs[o.name] = o

report = {c["tag"]: dict(hand_in_table=0.0, forearm_in_table=0.0, knee_hits_table=0.0, back_in_chair=0.0,
                         feet_below_floor=0.0, worst_t={}) for c, _, _ in chars}
t0, t1 = 2.5, FREEZE_AT
frames = list(range(int(t0 * FPS) + 1, int(t1 * FPS) + 1, STEP))
frames += list(range(int((SEG["empty"][1] + 17.2) * FPS), int(SEG["end"][1] * FPS), STEP))
for f in frames:
    sc.frame_set(f)
    t = (f - 1) / FPS
    for c, mesh, masks in chars:
        if mesh.hide_render:
            continue
        P = points(mesh)
        tag = c["tag"]
        r = report[tag]
        pel = P[masks["back"]].mean(0) if masks["back"].any() else P.mean(0)
        tab = nearest_table(pel[:2])
        top = tab["top"] + 0.004
        # hands / forearms below the table surface while over the table
        for key, field in (("hands", "hand_in_table"), ("forearm", "forearm_in_table")):
            Q = P[masks[key]]
            ins = inside(tab, Q[:, :2], 0.01) & (Q[:, 2] < top) & (Q[:, 2] > top - 0.10)
            d = float(top - Q[ins, 2].min()) if ins.any() else 0.0
            r.setdefault(field + "_series", []).append(round(d, 4))
            r["table"] = [round(tab["c"][0], 2), round(tab["c"][1], 2)]
            if d > r[field]:
                r[field] = d
                r["worst_t"][field] = round(t, 2)
        # knees / thighs vs the real underside (round: 2 cm top on a pedestal; rect: 2.6 cm top + 6.5 cm
        # apron around the edge, measured by ray casts) and vs the tablecloth hem band just outside the edge
        Q = P[masks["legs"]]
        if tab["kind"] == "round":
            under = np.full(len(Q), tab["top"] - 0.021)
        else:
            near_edge = ~inside(tab, Q[:, :2], 0.06)
            under = np.where(near_edge, tab["top"] - 0.066, tab["top"] - 0.027)
        ins = inside(tab, Q[:, :2], 0.0) & (Q[:, 2] > under)
        d = float((Q[ins, 2] - under[ins]).max()) if ins.any() else 0.0
        hem = (~inside(tab, Q[:, :2], 0.0)) & inside(tab, Q[:, :2], -0.025) & (Q[:, 2] > tab["top"] - 0.085) & (Q[:, 2] < tab["top"])
        if hem.any():
            d = max(d, float((Q[hem, 2] - (tab["top"] - 0.085)).max()))
        if d > r["knee_hits_table"]:
            r["knee_hits_table"] = d
            r["worst_t"]["knee_hits_table"] = round(t, 2)
        # back through the chair backrest (chair local +Y beyond the backrest front, 0.5..0.95 m high)
        ch = None
        best = 9
        for o in chairs.values():
            dd = (Vector(o.matrix_world.translation[:2]) - Vector(pel[:2])).length
            if dd < best:
                best, ch = dd, o
        if ch is not None and best < 0.45:
            Minv = np.array(ch.matrix_world.inverted())
            B = P[masks["back"]]
            L = B @ Minv[:3, :3].T + Minv[:3, 3]
            sel = (L[:, 2] > 0.5) & (L[:, 2] < 0.95) & (np.abs(L[:, 0]) < 0.2)
            # dining_chair_02 backrest leans back: front face y(z) measured by ray casts on the model
            yfront = np.interp(L[sel, 2], [0.50, 0.744, 0.815, 0.88, 0.949, 1.0], [0.125, 0.15, 0.175, 0.2, 0.225, 0.235])
            pen = L[sel, 1] - yfront - 0.006       # upholstery gives ~6 mm
            if len(pen) and pen.max() > r["back_in_chair"]:
                r["back_in_chair"] = float(pen.max())
                r["worst_t"]["back_in_chair"] = round(t, 2)
        d = float(-P[masks["feet"], 2].min()) if masks["feet"].any() else 0.0
        if d > r["feet_below_floor"]:
            r["feet_below_floor"] = d
            r["worst_t"]["feet_below_floor"] = round(t, 2)
for tag, r in report.items():
    s = np.maximum(np.array(r.pop("hand_in_table_series", [0])), np.array(r.pop("forearm_in_table_series", [0])))
    r["sink_p50"], r["sink_p90"] = float(np.percentile(s, 50)), float(np.percentile(s, 90))
json.dump(report, open(OUT, "w"), indent=1)
for tag, r in report.items():
    print(f"QA {tag:6s} sink p50={r['sink_p50']*100:4.1f} p90={r['sink_p90']*100:4.1f}cm | max hand={r['hand_in_table']*100:5.1f}cm forearm={r['forearm_in_table']*100:5.1f}cm "
          f"knee={r['knee_hits_table']*100:5.1f}cm back={r['back_in_chair']*100:5.1f}cm feet={r['feet_below_floor']*100:4.1f}cm "
          f"{r['worst_t']}")
