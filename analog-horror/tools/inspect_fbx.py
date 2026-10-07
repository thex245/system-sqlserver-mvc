"""Blender: import an FBX and print meshes, shape keys, bones and materials."""
import bpy, sys

argv = sys.argv[sys.argv.index("--") + 1:]
path = argv[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path, use_anim=False)
for ob in bpy.data.objects:
    line = f"{ob.type:9s} {ob.name:40s} parent={ob.parent.name if ob.parent else None}"
    if ob.type == "MESH":
        me = ob.data
        line += f" verts={len(me.vertices)} polys={len(me.polygons)} mats={[m.name for m in me.materials if m]}"
        if me.shape_keys:
            keys = [k.name for k in me.shape_keys.key_blocks]
            line += f"\n          shapekeys({len(keys)}): {keys}"
    if ob.type == "ARMATURE":
        bones = [b.name for b in ob.data.bones]
        line += f"\n          bones({len(bones)}): {bones}"
    print(line)
for m in bpy.data.materials:
    nodes = [n.image.name for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image] if m.use_nodes else []
    print("MAT", m.name, nodes, "blend", getattr(m, "blend_method", None))
