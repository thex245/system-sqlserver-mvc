"""SLIDE 07 — Incident 12, security camera, 1997.

A man sits on a chair in front of a containment cell. Behind the glass, the
specimen stands and watches him. It kneels down to his level and lays its hand flat
on the glass; he answers with his, palm to palm, each on their own side.

  0-9 s     "four hours" — small changes of posture (cut as a time-lapse in the edit)
  9.4-11 s  the specimen kneels by the glass
  11.4-13.8 s its hand rises and lies flat on the glass
  14.5-18 s the man raises his hand to meet it
  18-21 s   hold

Renders at 60 fps (time-lapse part every 12th frame).
Outputs build/renders/cell/#####.png + track.json
usage: python3 scene_cell.py [--preview]
"""
import math
import sys

import bpy
from mathutils import Vector

import cast
import rig
from rig import v

PREVIEW = "--preview" in sys.argv
rig.reset_scene()
sc = bpy.context.scene
sc.render.fps = 60
FPS = 60


def sec(t):
    return int(round(t * FPS)) + 1


# ---------------------------------------------------------------- set
cell_tiles = rig.tile_material("cell_tiles", tile=(0.62, 0.66, 0.64), grout=(0.25, 0.27, 0.26), scale=3.0, dirt=0.6,
                               axes=("X", "Z"))
cell_tiles_y = rig.tile_material("cell_tiles_y", tile=(0.62, 0.66, 0.64), grout=(0.25, 0.27, 0.26), scale=3.0,
                                 dirt=0.6, axes=("Y", "Z"))
obs_wall = rig.noise_material("obs_wall", (0.14, 0.15, 0.15), (0.24, 0.25, 0.24), scale=5, rough=0.8, bump=0.05)
floor_m = rig.noise_material("floor", (0.07, 0.07, 0.07), (0.2, 0.2, 0.19), scale=9, rough=0.6, bump=0.15,
                             distortion=0.5)
steel = rig.principled("steel", (0.12, 0.13, 0.14), rough=0.35, metallic=0.6)
chair_m = rig.principled("chair", (0.05, 0.05, 0.05), rough=0.5, metallic=0.3)
H = 2.8
rig.box("floor", (6, 7, 0.1), (0, 0, -0.05), floor_m)
rig.box("ceiling", (6, 7, 0.1), (0, 0, H + 0.05), obs_wall)
rig.box("cell_back", (5, 0.1, H), (0, 3.05, H / 2), cell_tiles)
rig.box("cell_l", (0.1, 3, H), (-2.5, 1.5, H / 2), cell_tiles_y)
rig.box("cell_r", (0.1, 3, H), (2.5, 1.5, H / 2), cell_tiles_y)
rig.box("obs_l", (0.1, 3.5, H), (-2.5, -1.75, H / 2), obs_wall)
rig.box("obs_r", (0.1, 3.5, H), (2.5, -1.75, H / 2), obs_wall)
rig.box("obs_back", (5, 0.1, H), (0, -3.5, H / 2), obs_wall)
# the glass wall: thin transparent pane with a faint reflection, in a steel frame
gm = bpy.data.materials.new("glass")
gm.use_nodes = True
nt = gm.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
tr = nt.nodes.new("ShaderNodeBsdfTransparent")
tr.inputs["Color"].default_value = (0.86, 0.93, 0.9, 1)
gl = nt.nodes.new("ShaderNodeBsdfGlossy")
gl.inputs["Roughness"].default_value = 0.04
mix = nt.nodes.new("ShaderNodeMixShader")
mix.inputs[0].default_value = 0.07
nt.links.new(tr.outputs[0], mix.inputs[1])
nt.links.new(gl.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
rig.box("glass", (4.4, 0.02, 2.3), (0, 0, 1.35), gm)
rig.box("sill", (5, 0.3, 0.2), (0, 0, 0.1), steel)
rig.box("head", (5, 0.3, 0.3), (0, 0, H - 0.15), steel)
for x in (-2.3, -0.75, 0.75, 2.3):
    rig.box(f"mullion{x}", (0.08, 0.12, 2.4), (x, 0, 1.35), steel)
# chair
CH = Vector((-0.4, -0.52, 0))
rig.box("seat", (0.45, 0.42, 0.04), (CH.x, CH.y, 0.46), chair_m)
rig.box("back", (0.45, 0.04, 0.45), (CH.x, CH.y - 0.2, 0.72), chair_m)
for dx in (-0.2, 0.2):
    for dy in (-0.18, 0.18):
        rig.box(f"leg{dx}{dy}", (0.03, 0.03, 0.46), (CH.x + dx, CH.y + dy, 0.23), chair_m)
# lights
cell_light = rig.area_light("cell", (0, 1.6, H - 0.06), (0, 0, 0), 1.4, 230, color=(0.86, 1.0, 0.92), size_y=0.3)
rig.box("cell_fix", (1.4, 0.3, 0.04), (0, 1.6, H - 0.02),
        rig.principled("tube", (1, 1, 1), emission=((0.86, 1.0, 0.92), 8.0)))
rig.area_light("obs", (0.8, -2.2, H - 0.06), (0, 0, 0), 0.6, 14, color=(1.0, 0.9, 0.75))
rig.world((0, 0, 0), 0)

# ---------------------------------------------------------------- the man (normal proportions, dark clothes)
man = rig.Character("Xbot.glb", "man")
man.material(rig.principled("clothes", (0.045, 0.05, 0.06), rough=0.75))
man.root.location = CH + Vector((0, 0.05, 0))
man.root.rotation_euler = (0, 0, math.pi)          # faces the glass (+Y)
bpy.context.view_layer.update()
SIT = {"LeftUpLeg": v(0.12, -1, 0.04), "RightUpLeg": v(-0.12, -1, 0.04), "LeftLeg": v(0.03, -0.1, -1),
       "RightLeg": v(-0.03, -0.1, -1), "LeftFoot": v(0, -1, -0.3), "RightFoot": v(0, -1, -0.3),
       "Spine": v(0, -0.12, 1), "Spine1": v(0, -0.1, 1), "Spine2": v(0, -0.08, 1), "Neck": v(0, -0.15, 1),
       "LeftArm": v(0.18, -0.45, -1), "LeftForeArm": v(0.05, -1, -0.2), "LeftHand": v(0, -1, -0.3),
       "RightArm": v(-0.18, -0.45, -1), "RightForeArm": v(-0.05, -1, -0.2), "RightHand": v(0, -1, -0.3),
       "look": v(0, -1, 0.08), "fingers": 0.35}
SIT_HIPS = (0, 0.1, -0.5)


MEET = Vector((0.16, 0.0, 1.24))      # the spot on the glass where the two hands meet


def man_pose(frame, look=(0, -1, 0.08), spine=(0, -0.12, 1), hand=None, lean=0.0):
    p = dict(SIT, look=v(*look), Spine=v(*spine))
    if lean:
        p["Spine1"] = v(0, -0.12 - lean, 1)
        p["Spine2"] = v(0, -0.1 - lean, 1)
    man.pose(p, hips=SIT_HIPS)
    if hand is not None:
        h, flat = hand
        man.ik_arm("Right", h, pole=Vector((0.6, -0.3, -1.0)), hand_dir=Vector((0.05, 0.0, 1.0)))
        if flat:
            man.orient_palm("Right", Vector((0, 1, 0)))      # palm against the glass
        man.curl_fingers(0.0 if flat else 0.25, side=("Right",))
    man.key(frame)


# ---------------------------------------------------------------- the specimen
c = cast.make_creature("p12")
cast.add_smile(c)
C_POS = Vector((-0.3, 0.34, 0))
c.root.location = C_POS
bpy.context.view_layer.update()
KNEEL_UP = dict(cast.ARMS_DOWN, **{
    "LeftUpLeg": v(0.12, 0.05, -1), "RightUpLeg": v(-0.12, 0.05, -1), "LeftLeg": v(0, 1, -0.08),
    "RightLeg": v(0, 1, -0.08), "LeftFoot": v(0, 1, -0.5), "RightFoot": v(0, 1, -0.5),
    "Spine": v(0, -0.08, 1), "Spine1": v(0, -0.1, 1), "Spine2": v(0, -0.1, 1), "Neck": v(0, -0.2, 1), "fingers": 0.1})
KNEEL_HIPS = (0, 0.05, -0.56)


def c_pose(frame, look=(0, -1, -0.15), hand=None, tilt=0.0, kneel=False, roll=0.0):
    base = KNEEL_UP if kneel else cast.STAND
    p = dict(base, look=v(look[0] + tilt, look[1], look[2]), roll=roll)
    c.pose(p, hips=KNEEL_HIPS if kneel else (0, 0, 0))
    if hand is not None:
        h, flat = hand
        c.ik_arm("Left", h, pole=Vector((0.5, 0.2, -1.0)), hand_dir=Vector((0.05, 0.0, 1.0)))
        if flat:
            c.orient_palm("Left", Vector((0, -1, 0)))
        c.curl_fingers(0.0 if flat else 0.2, side=("Left",))
    c.key(frame)


# 0-9 s: four hours, compressed. Small changes between keys read as time-lapse jumps.
for t, (cl, ml, sp) in zip([0, 1.5, 3, 4.5, 6, 7.5, 9],
                           [((0.0, -1, -0.25), (0, -1, -0.05), (0, -0.1, 1)),
                            ((0.25, -1, -0.2), (0.1, -1, 0.1), (0, -0.25, 1)),
                            ((-0.2, -1, -0.15), (0, -1, -0.3), (0, -0.35, 1)),
                            ((0.1, -1, -0.3), (-0.1, -1, 0.1), (0, -0.05, 1)),
                            ((0.35, -1, -0.2), (0, -1, 0.05), (0, -0.2, 1)),
                            ((-0.1, -1, -0.25), (0.05, -1, 0.1), (0, -0.15, 1)),
                            ((0.0, -1, -0.2), (0, -1, 0.08), (0, -0.12, 1))]):
    c_pose(sec(t), look=cl)
    man_pose(sec(t), look=ml, spine=sp)
# 9-11 s: it kneels down by the glass, level with him
c_pose(sec(9.4), look=(0.0, -1, -0.2))
c_pose(sec(11.0), look=(0.0, -1, 0.0), kneel=True)
# 11.3-13.8 s: it raises its hand and lays it flat on the glass
C_HAND = MEET + Vector((0, 0.045, -0.06))
c_pose(sec(11.4), look=(0.0, -1, 0.0), kneel=True)
c_pose(sec(12.6), look=(-0.03, -1, 0.02), kneel=True, hand=(C_HAND + Vector((0.05, 0.16, -0.12)), False))
c_pose(sec(13.8), look=(-0.05, -1, 0.02), kneel=True, hand=(C_HAND, True))
c_pose(sec(16.5), look=(-0.08, -1, 0.03), kneel=True, hand=(C_HAND, True), roll=-6)
c_pose(sec(23.0), look=(-0.1, -1, 0.04), kneel=True, hand=(C_HAND, True), roll=-12)
# 14.5-18 s: he answers it, palm to palm from his side of the glass
M_HAND = MEET + Vector((0, -0.06, -0.06))
man_pose(sec(14.5), look=(0, -1, 0.12))
man_pose(sec(16.2), look=(0, -1, 0.14), spine=(0, -0.25, 1), hand=(M_HAND + Vector((0.04, -0.2, -0.16)), False),
         lean=0.1)
man_pose(sec(18.0), look=(0, -1, 0.15), spine=(0, -0.3, 1), hand=(M_HAND, True), lean=0.15)
man_pose(sec(23.0), look=(0, -1, 0.16), spine=(0, -0.31, 1), hand=(M_HAND, True), lean=0.16)
cast.key_smile(c, sec(0), 0.0)

# ---------------------------------------------------------------- camera
cam = rig.camera("cam", (1.25, -2.5, 2.45), (-0.5, 0.05, 1.05), lens=21)
sc.camera = cam
rig.render_settings(res=(320, 240) if PREVIEW else (512, 384), samples=4 if PREVIEW else 6, exposure=-0.3)
sc.cycles.use_fast_gi = True
sc.cycles.diffuse_bounces = 2
sc.cycles.glossy_bounces = 1
out = rig.out_dir("cell")
if "--empty" in sys.argv:
    # the morning after: both of them gone, the chair still facing the glass
    for o in list(bpy.data.objects):
        top = o
        while top.parent:
            top = top.parent
        if top.name in ("man", "p12"):
            o.hide_render = True
    sc.cycles.samples = 48
    sc.frame_set(sec(0))
    sc.render.filepath = str(rig.out_dir("stills") / "cell_empty.png")
    bpy.ops.render.render(write_still=True)
    sys.exit(0)
if PREVIEW:
    frames = [sec(x) for x in ([float(a) for a in __import__('os').environ['CELL_T'].split(',')] if 'CELL_T' in __import__('os').environ else (0, 3, 10.2, 11.5, 12.6, 13.8, 15.5, 16.5, 18.0, 20.0))]
elif "--frames" in sys.argv:
    i = sys.argv.index("--frames")
    step = int(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else 1
    frames = list(range(int(sys.argv[i + 1]), int(sys.argv[i + 2]) + 1, step))
else:
    frames = list(range(sec(0), sec(9), 12)) + list(range(sec(9), sec(21) + 1))
track = {}
for f in frames:
    sc.frame_set(f)
    track[f] = {"creature": rig.head_box(c, cam), "man": rig.head_box(man, cam), "meet": rig.screen_pos(cam, MEET)}
    sc.render.filepath = str(out / f"{f:05d}.png")
    bpy.ops.render.render(write_still=True)
    print("frame", f, flush=True)
tp = out / ("track_preview.json" if PREVIEW else "track.json")
old = __import__("json").loads(tp.read_text()) if tp.exists() else {}
old.update({str(k): val for k, val in track.items()})
rig.write_json(tp, old)
