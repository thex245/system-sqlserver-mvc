"""Drop shape keys that are never animated (keeps Basis + animated keys). Run on film.blend:
blender -b film.blend --python trim_scene.py"""
import bpy

total = 0
for me in bpy.data.meshes:
    key = me.shape_keys
    if not key:
        continue
    animated = set()
    ad = key.animation_data
    if ad and ad.action:
        for layer in getattr(ad.action, "layers", []):
            for st in layer.strips:
                for cb in st.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path.startswith('key_blocks["'):
                            animated.add(fc.data_path.split('"')[1])
    ob = next((o for o in bpy.data.objects if o.data == me), None)
    if ob is None:
        continue
    for kb in list(key.key_blocks)[1:]:
        if kb.name not in animated:
            ob.shape_key_remove(kb)
            total += 1
print("TRIM removed shape keys:", total)
bpy.ops.wm.save_mainfile(compress=True)
