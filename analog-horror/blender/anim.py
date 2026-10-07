"""Rocketbox mocap -> avatar retargeting (world-space rotation copy + pelvis location), baked
into per-avatar actions that are then layered with NLA strips.
"""
import os
import bpy

ANIM_ROOT = os.environ.get("VAMA_ANIMS", r"D:\VAMA_work\assets\rocketbox\Assets\Animations")
FACE_BONES = {"Bip01 MJaw", "Bip01 MBottomLip", "Bip01 MTongue", "Bip01 LMouthBottom", "Bip01 RMouthBottom",
              "Bip01 RMasseter", "Bip01 LMasseter", "Bip01 MUpperLip", "Bip01 RCaninus", "Bip01 LCaninus",
              "Bip01 REyeBlinkBottom", "Bip01 LEyeBlinkBottom", "Bip01 RUpperlip", "Bip01 LUpperlip",
              "Bip01 RMouthCorner", "Bip01 LMouthCorner", "Bip01 RCheek", "Bip01 LCheek", "Bip01 REyeBlinkTop",
              "Bip01 LEyeBlinkTop", "Bip01 RInnerEyebrow", "Bip01 LInnerEyebrow", "Bip01 MMiddleEyebrow",
              "Bip01 ROuterEyebrow", "Bip01 LOuterEyebrow", "Bip01 MNose", "Bip01 REye", "Bip01 LEye"}


def clip_path(name):
    for sub in ("all_animations_max_motextr_static", "all_animations_max_motextr_xyz", "all_animations_max_motextr_xy"):
        p = os.path.join(ANIM_ROOT, sub, f"{name}.max.fbx")
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def rest_matrix(avatar_arm):
    """Canonical rig transform: origin, imported rotation (-90 deg Z) and 0.01 scale.
    A character with identity placement faces world -Y."""
    from mathutils import Matrix, Euler
    rot = Euler((0.0, 0.0, -1.5707963), "XYZ").to_matrix().to_4x4()
    return rot @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0))


def import_clip(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=clip_path(name), use_anim=True, ignore_leaf_bones=False,
                             automatic_bone_orientation=False)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o is not arm:
            bpy.data.objects.remove(o, do_unlink=True)
    return arm


def _select_only(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def bake_clip(avatar_arm, name, frames=None, action_name=None, step=1, cycles=None):
    """Retarget clip `name` onto avatar_arm; returns a new Action (frames start at 1).
    cycles=N loops the clip N times, accumulating root motion (for walk cycles)."""
    clip = import_clip(name)
    act = clip.animation_data.action
    if cycles:
        n = int(act.frame_range[1] - act.frame_range[0])
        for fc in _fcurves(act):
            m = fc.modifiers.new("CYCLES")
            off = fc.data_path == "location"
            m.mode_before = m.mode_after = "REPEAT_OFFSET" if off else "REPEAT"
        frames = (int(act.frame_range[0]), int(act.frame_range[0]) + n * cycles)
    f0, f1 = (int(act.frame_range[0]), int(act.frame_range[1])) if frames is None else frames
    # The avatar rig is normalised to the world origin (see rbx.import_avatar) and the clip keeps
    # its own imported root transform/animation, so the world-space copy carries root motion and
    # the real seat/floor heights. Avatars must not be parented while baking.
    saved_parent = avatar_arm.parent
    saved_mw = avatar_arm.matrix_world.copy()
    avatar_arm.parent = None
    avatar_arm.matrix_world = rest_matrix(avatar_arm)
    saved = (None, None, avatar_arm.animation_data.action if avatar_arm.animation_data else None)
    if avatar_arm.animation_data:
        avatar_arm.animation_data.action = None
    cons = []
    for pb in avatar_arm.pose.bones:
        if pb.name in FACE_BONES or pb.name not in clip.pose.bones:
            continue
        c = pb.constraints.new("COPY_ROTATION")
        c.target, c.subtarget = clip, pb.name
        c.target_space = c.owner_space = "WORLD"
        cons.append((pb, c))
        if pb.name == "Bip01 Pelvis":
            c2 = pb.constraints.new("COPY_LOCATION")
            c2.target, c2.subtarget = clip, pb.name
            c2.target_space = c2.owner_space = "WORLD"
            cons.append((pb, c2))
    _select_only(avatar_arm)
    bpy.ops.object.mode_set(mode="POSE")
    for pb in avatar_arm.pose.bones:
        sel = pb.name not in FACE_BONES
        if hasattr(pb, "select"):
            pb.select = sel  # Blender 5.x
        else:
            pb.bone.select = sel
    bpy.ops.nla.bake(frame_start=f0, frame_end=f1, step=step, only_selected=True, visual_keying=True,
                     clear_constraints=True, use_current_action=False, bake_types={"POSE"})
    bpy.ops.object.mode_set(mode="OBJECT")
    baked = avatar_arm.animation_data.action
    baked.name = action_name or f"{avatar_arm.get('vama_tag', avatar_arm.name)}:{name}"
    # shift so the clip starts at frame 1
    for fc in _fcurves(baked):
        for kp in fc.keyframe_points:
            kp.co.x -= f0 - 1
            kp.handle_left.x -= f0 - 1
            kp.handle_right.x -= f0 - 1
    baked.use_fake_user = True
    avatar_arm.animation_data.action = saved[2]
    avatar_arm.parent = saved_parent
    avatar_arm.matrix_world = saved_mw
    bpy.data.objects.remove(clip, do_unlink=True)
    for a in list(bpy.data.actions):
        if a.users == 0 and a is not baked and not a.use_fake_user:
            bpy.data.actions.remove(a)
    return baked


def _fcurves(action):
    """Blender 5.x layered actions: iterate all fcurves of the action's channelbags."""
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out
