"""Blender: inspect Rocketbox animation FBX files (objects, action range, root motion)."""
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:]
for path in argv:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, use_anim=True, ignore_leaf_bones=False, automatic_bone_orientation=False)
    sc = bpy.context.scene
    objs = [(o.name, o.type, len(o.data.bones) if o.type == "ARMATURE" else "") for o in bpy.data.objects]
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    act = arm.animation_data.action if arm and arm.animation_data else None
    print("FILE", os.path.basename(path), "fps", sc.render.fps, "objs", objs)
    if act:
        print("  action", act.name, "range", tuple(act.frame_range), "scale", tuple(arm.scale))
        pb = arm.pose.bones.get("Bip01 Pelvis") or arm.pose.bones[0]
        for f in (int(act.frame_range[0]), int(act.frame_range[1])):
            sc.frame_set(f)
            m = arm.matrix_world @ pb.matrix
            print("   frame", f, "pelvis world", tuple(round(v, 3) for v in m.translation))
