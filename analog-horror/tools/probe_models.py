"""Blender: import each Poly Haven glTF and print its dimensions and parts."""
import bpy, os, sys
sys.path.insert(0, r"D:\Projetos\system-sqlserver-mvc\analog-horror\blender")
import setlib
root = os.path.join(setlib.PH, "models")
for aid in sorted(os.listdir(root)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    c = bpy.context.scene.collection
    r, objs = setlib.import_gltf(aid, c)
    mn, mx = setlib.bounds(objs)
    meshes = [o for o in objs if o.type == "MESH"]
    print(f"MODEL {aid:28s} size=({mx.x-mn.x:.3f},{mx.y-mn.y:.3f},{mx.z-mn.z:.3f}) min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) "
          f"parts={[o.name for o in meshes][:8]} polys={sum(len(o.data.polygons) for o in meshes)}")
