"""Shrink baked actions in a character .blend: drop scale + non-pelvis location channels and
decimate keys (CCTV renders every 2nd frame). blender -b X.blend --python slim_actions.py -- STEP"""
import sys
import numpy as np
import bpy

step = int(sys.argv[sys.argv.index("--") + 1])


def bags(act):
    for layer in getattr(act, "layers", []):
        for st in layer.strips:
            for cb in st.channelbags:
                yield cb


before = after = 0
for act in bpy.data.actions:
    for cb in bags(act):
        for fc in list(cb.fcurves):
            n = len(fc.keyframe_points)
            before += n
            dp = fc.data_path
            if dp.endswith(".scale") or (dp.endswith(".location") and "Bip01 Pelvis" not in dp):
                cb.fcurves.remove(fc)
                continue
            co = np.empty(n * 2, dtype=np.float32)
            fc.keyframe_points.foreach_get("co", co)
            co = co.reshape(-1, 2)
            keep = ((np.round(co[:, 0]) - 1) % step == 0)
            keep[-1] = True
            co = co[keep]
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(co))
            fc.keyframe_points.foreach_set("co", co.ravel())
            fc.keyframe_points.foreach_set("interpolation", np.full(len(co), 2, dtype=np.int32))
            fc.update()
            after += len(co)
print("SLIM", bpy.data.filepath, before, "->", after)
bpy.ops.wm.save_mainfile(compress=True)
