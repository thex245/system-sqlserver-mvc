"""Render face close-ups of candidate avatars (neutral + expressions) for casting/QA."""
import os, sys, math
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import rbx

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = argv[0]
names = argv[1:]

EXPR = {
    "neutral": {},
    "smile": {"AK_44_MouthSmileLeft": 0.7, "AK_45_MouthSmileRight": 0.7, "AK_07_CheekSquintLeft": 0.3, "AK_08_CheekSquintRight": 0.3},
    "fear": {"AK_03_BrowInnerUp": 0.9, "AK_21_EyeWideLeft": 0.7, "AK_22_EyeWideRight": 0.7, "AK_25_JawOpen": 0.25,
             "AK_46_MouthStretchLeft": 0.5, "AK_47_MouthStretchRight": 0.5},
    "shout": {"AK_25_JawOpen": 0.75, "AK_01_BrowDownLeft": 0.8, "AK_02_BrowDownRight": 0.8, "AK_48_MouthUpperUpLeft": 0.5,
              "AK_49_MouthUpperUpRight": 0.5, "AK_50_NoseSneerLeft": 0.4, "AK_51_NoseSneerRight": 0.4},
    "viseme_O": {"AA_VI_13_O": 1.0},
}


def setup_render():
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = 512
    sc.render.resolution_y = 640
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.eevee.taa_render_samples = 64
    try:
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.025, 1)
    sc.world = w


def light(name, loc, energy, size, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA")
    l.energy = energy
    l.size = size
    l.color = color
    o = bpy.data.objects.new(name, l)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def aim(obj, target):
    d = target - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render()
    arm, mesh = rbx.import_avatar(name)
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    head = mw @ arm.data.bones["Bip01 Head"].head_local
    le = mw @ arm.data.bones["Bip01 LEye"].head_local
    re = mw @ arm.data.bones["Bip01 REye"].head_local
    eyes = (le + re) / 2
    fwd = eyes - head
    fwd.z = 0
    fwd.normalize()
    target = eyes + Vector((0, 0, -0.03))
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 85
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = target + fwd * 0.75 + Vector((0, 0, 0.02))
    aim(cam, target)
    bpy.context.scene.camera = cam
    side = fwd.cross(Vector((0, 0, 1)))
    k = light("key", target + fwd * 0.8 + side * 0.6 + Vector((0, 0, 0.4)), 60, 0.6, (1.0, 0.92, 0.82))
    aim(k, target)
    f = light("fill", target + fwd * 0.8 - side * 0.8, 15, 1.0, (0.8, 0.88, 1.0))
    aim(f, target)
    r = light("rim", target - fwd * 0.6 + side * 0.3 + Vector((0, 0, 0.5)), 40, 0.4)
    aim(r, target)
    print("SCALE", name, arm.scale[:], "head", head, "fwd", fwd)
    for ename, vals in EXPR.items():
        for kb in mesh.data.shape_keys.key_blocks:
            kb.value = 0.0
        rbx.set_keys(mesh, vals)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"{name}__{ename}.png")
        bpy.ops.render.render(write_still=True)
