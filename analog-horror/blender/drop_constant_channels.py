"""Lossless: remove animation channels whose value never changes (max deviation < 1e-6) and keep
their value as the static pose. Every varying channel keeps every key.
blender -b X.blend --python drop_constant_channels.py"""
import numpy as np
import bpy

removed = kept = 0
for act in bpy.data.actions:
    for layer in getattr(act, "layers", []):
        for st in layer.strips:
            for cb in st.channelbags:
                for fc in list(cb.fcurves):
                    n = len(fc.keyframe_points)
                    co = np.empty(n * 2, dtype=np.float64)
                    fc.keyframe_points.foreach_get("co", co)
                    v = co[1::2]
                    # a constant channel equal to the rest value (0 for loc offsets / 1 for scale) is a no-op
                    rest = 1.0 if fc.data_path.endswith(".scale") else 0.0
                    # (bone-space units are centimetres: 1e-4 = one micrometre / 0.01 % scale)
                    if n and np.max(np.abs(v - rest)) < 1e-4:
                        cb.fcurves.remove(fc)
                        removed += 1
                    else:
                        kept += 1
print("CONST", bpy.data.filepath, "removed", removed, "kept", kept)
bpy.ops.wm.save_mainfile(compress=True)
