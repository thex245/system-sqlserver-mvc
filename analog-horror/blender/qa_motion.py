"""Motion QA: catch spins, flips, twisted wrists and inverted elbows (no rendering).

blender -b film.blend --python qa_motion.py -- OUT.json tags(comma) [step] [t0 t1]
Per bone and frame: angular speed (deg/s) and per-frame jump; forearm/hand twist about the limb axis
(Biped limb axis = local X) relative to the parent; elbow flexion and its bending side.
"""
import json, math, os, sys
import numpy as np
import bpy
from mathutils import Matrix

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from timeline import FPS, SEG, FREEZE_AT

a = sys.argv[sys.argv.index("--") + 1:]
OUT, TAGS = a[0], a[1].split(",")
STEP = int(a[2]) if len(a) > 2 else 1
T0 = float(a[3]) if len(a) > 3 else 2.5
T1 = float(a[4]) if len(a) > 4 else FREEZE_AT - 0.05
sc = bpy.context.scene

# Keep only what is being checked (this QA run is never saved).
keep = set()
for t in TAGS:
    keep |= {f"{t}_rig", f"{t}_body", f"{t}_root"}
for o in list(bpy.data.objects):
    if o.name.endswith(("_rig", "_body")) and o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
    elif o.type == "MESH" and not o.name.endswith("_body"):
        o.hide_viewport = True

BONES = ["Bip01 Pelvis", "Bip01 Spine1", "Bip01 Spine2", "Bip01 Neck", "Bip01 Head"]
for s in ("L", "R"):
    BONES += [f"Bip01 {s} Clavicle", f"Bip01 {s} UpperArm", f"Bip01 {s} Forearm", f"Bip01 {s} Hand"]
PARENT = {f"Bip01 {s} {b}": f"Bip01 {s} {p}" for s in ("L", "R") for b, p in (("Forearm", "UpperArm"), ("Hand", "Forearm"))}


def rot(arm, b):
    m = (arm.matrix_world @ arm.pose.bones[b].matrix).to_3x3().normalized()
    return np.array(m)


def angle_between(R1, R2):
    c = (np.trace(R1.T @ R2) - 1) / 2
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def twist(Rp, Rc):
    """Rotation of the child about its own limb axis (X) relative to the parent's frame."""
    Rl = Rp.T @ Rc
    q = Matrix(Rl.tolist()).to_quaternion()
    ang = 2 * math.degrees(math.atan2(q.x, q.w))            # swing-twist: twist part about X
    return (ang + 180) % 360 - 180


arms = {t: bpy.data.objects[f"{t}_rig"] for t in TAGS if f"{t}_rig" in bpy.data.objects}
# twist is measured relative to the rest pose (Biped hand/forearm frames are offset at rest)
REST_TWIST = {}
for tag, arm in arms.items():
    for b, p in PARENT.items():
        Rp = np.array(arm.data.bones[p].matrix_local.to_3x3().normalized())
        Rc = np.array(arm.data.bones[b].matrix_local.to_3x3().normalized())
        REST_TWIST[(tag, b)] = twist(Rp, Rc)
prev = {}
rep = {t: {"max_speed": {}, "jumps": [], "twist": [], "elbow": [], "spins": []} for t in arms}
frames = range(int(T0 * FPS) + 1, int(T1 * FPS) + 1, STEP)
cuts = {int(SEG[s][1] * FPS) + 1 for s in SEG}          # discontinuities are expected on cuts
for f in frames:
    sc.frame_set(f)
    t = (f - 1) / FPS
    for tag, arm in arms.items():
        cur = {b: rot(arm, b) for b in BONES if b in arm.pose.bones}
        if tag in prev and not any(abs(f - c) <= STEP for c in cuts):
            for b, R in cur.items():
                d = angle_between(prev[tag][b], R)
                speed = d * FPS / STEP
                ms = rep[tag]["max_speed"]
                if speed > ms.get(b, (0, 0))[0]:
                    ms[b] = (round(speed, 1), round(t, 2))
                limit = 35 if ("Hand" in b or "Forearm" in b or "UpperArm" in b) else 20
                if d > limit * STEP:
                    rep[tag]["jumps"].append((round(t, 2), b, round(d, 1)))
        for b, p in PARENT.items():
            if b in cur and p in cur:
                tw = (twist(cur[p], cur[b]) - REST_TWIST[(tag, b)] + 180) % 360 - 180
                if abs(tw) > 100:
                    rep[tag]["twist"].append((round(t, 2), b, round(tw, 1)))
        for s in ("L", "R"):
            ua, fa = cur.get(f"Bip01 {s} UpperArm"), cur.get(f"Bip01 {s} Forearm")
            if ua is not None:
                flex = angle_between(np.eye(3), np.eye(3))
                da, db_ = ua[:, 0], fa[:, 0]
                flex = math.degrees(math.acos(max(-1, min(1, float(np.dot(da, db_))))))
                side = float(np.dot(np.cross(da, db_), ua[:, 2]))
                if flex > 155 or (flex > 25 and side > 0.15):
                    rep[tag]["elbow"].append((round(t, 2), s, round(flex, 1), round(side, 2)))
        prev[tag] = cur
for tag, r in rep.items():
    for k in ("jumps", "twist", "elbow"):
        r[k + "_count"] = len(r[k])
        r[k] = r[k][:40]
json.dump(rep, open(OUT, "w"), indent=1)
for tag, r in rep.items():
    top = sorted(r["max_speed"].items(), key=lambda kv: -kv[1][0])[:4]
    print(f"MOTION {tag:6s} jumps={r['jumps_count']} twist>100={r['twist_count']} elbow_flags={r['elbow_count']} "
          f"fastest={[(b.replace('Bip01 ', ''), v) for b, v in top]}")
    for k in ("jumps", "twist", "elbow"):
        if r[k]:
            print("   ", k, r[k][:8])
