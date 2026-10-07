"""Lossless clean-up of baked actions (run on each chars/<tag>.blend):

1. Quaternion continuity: q and -q are the same rotation, but interpolating between keys of opposite
   sign (or NLA-blending two clips stored in opposite hemispheres) makes a limb spin the long way
   round. Every key is put in the hemisphere of the previous key, and each action starts with w >= 0
   so different clips share one convention.
2. Channels whose value never leaves its rest value (|dev| < 1e-4) are removed (no-ops).
blender -b X.blend --python prep_actions.py
"""
import re
import numpy as np
import bpy

flips = removed = 0
for act in bpy.data.actions:
    for layer in getattr(act, "layers", []):
        for st in layer.strips:
            for cb in st.channelbags:
                quats = {}
                for fc in list(cb.fcurves):
                    m = re.match(r'pose\.bones\["(.+)"\]\.rotation_quaternion', fc.data_path)
                    if m:
                        quats.setdefault(m.group(1), {})[fc.array_index] = fc
                for bone, chans in quats.items():
                    if len(chans) != 4:
                        continue
                    arrs = []
                    for i in range(4):
                        fc = chans[i]
                        co = np.empty(len(fc.keyframe_points) * 2, dtype=np.float64)
                        fc.keyframe_points.foreach_get("co", co)
                        arrs.append(co.reshape(-1, 2))
                    n = min(len(a) for a in arrs)
                    if n == 0 or any(len(a) != n for a in arrs):
                        continue
                    Q = np.stack([a[:, 1] for a in arrs], 1)
                    if Q[0, 0] < 0:
                        Q[0] *= -1
                    for k in range(1, n):
                        if np.dot(Q[k], Q[k - 1]) < 0:
                            Q[k] *= -1
                            flips += 1
                    for i in range(4):
                        arrs[i][:, 1] = Q[:, i]
                        chans[i].keyframe_points.foreach_set("co", arrs[i].ravel())
                        chans[i].update()
                for fc in list(cb.fcurves):
                    n = len(fc.keyframe_points)
                    if not n or "rotation_quaternion" in fc.data_path:
                        continue
                    co = np.empty(n * 2, dtype=np.float64)
                    fc.keyframe_points.foreach_get("co", co)
                    rest = 1.0 if fc.data_path.endswith(".scale") else 0.0
                    if np.max(np.abs(co[1::2] - rest)) < 1e-4:
                        cb.fcurves.remove(fc)
                        removed += 1
print("PREP", bpy.data.filepath, "sign flips fixed:", flips, "constant channels removed:", removed)
bpy.ops.wm.save_mainfile(compress=True)
