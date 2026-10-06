"""SLIDE 07 — Incident 12, security camera, 1997.

A man sits on a chair in front of a containment cell. Behind the glass, the
specimen stands and watches him. It lays its hand on the glass; he does the same,
on the same spot.

  0-9 s    "four hours" — small changes of posture (cut as a time-lapse in the edit)
  9-13 s   the specimen raises its hand to the glass
  14.5-18 s the man raises his hand to meet it
  18-22 s  hold

Outputs build/renders/cell/####.png + track.json
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
sc.render.fps = 30
FPS = 30


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
CH = Vector((-0.35, -0.62, 0))
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


def man_pose(frame, look=(0, -1, 0.08), spine=(0, -0.12, 1), hand=None):
    p = dict(SIT, look=v(*look), Spine=v(*spine))
    man.pose(p, hips=SIT_HIPS)
    if hand is not None:
        man.ik_arm("Right", hand, pole=Vector((0.4, 0.0, -1.0)), hand_dir=Vector((0.0, 0.25, 1.0)))
        man.curl_fingers(0.0, side=("Right",))
    man.key(frame)


# ---------------------------------------------------------------- the specimen
c = cast.make_creature("p12")
cast.add_smile(c)
C_POS = Vector((-0.42, 0.42, 0))
c.root.location = C_POS
bpy.context.view_layer.update()
GLASS_PT = Vector((-0.1, -0.012, 1.36))      # the spot both hands meet (creature side)


def c_pose(frame, look=(0, -1, -0.15), hand=None, tilt=0.0):
    p = dict(cast.STAND, look=v(look[0] + tilt, look[1], look[2]))
    c.pose(p)
    if hand is not None:
        c.ik_arm("Left", hand, pole=Vector((0.5, 0.2, -1.0)), hand_dir=Vector((0.0, -0.25, 1.0)))
        c.curl_fingers(0.0, side=("Left",))
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
# 9-13 s: its hand rises to the glass
c_pose(sec(10.0), look=(0.0, -1, -0.2))
c_pose(sec(13.0), look=(-0.05, -1, -0.18), hand=GLASS_PT)
c_pose(sec(16.0), look=(-0.12, -1, -0.15), hand=GLASS_PT, tilt=-0.1)
c_pose(sec(22.0), look=(-0.18, -1, -0.12), hand=GLASS_PT, tilt=-0.2)
# 14.5-18 s: he answers it, on the same spot from his side
man_pose(sec(14.5), look=(0, -1, 0.12))
man_pose(sec(18.0), look=(0, -1, 0.15), spine=(0, -0.35, 1), hand=GLASS_PT + Vector((0, -0.03, 0)))
man_pose(sec(22.0), look=(0, -1, 0.16), spine=(0, -0.36, 1), hand=GLASS_PT + Vector((0, -0.03, 0)))
cast.key_smile(c, sec(0), 0.0)

# ---------------------------------------------------------------- camera
cam = rig.camera("cam", (1.25, -2.5, 2.45), (-0.5, 0.05, 1.05), lens=21)
sc.camera = cam
rig.render_settings(res=(640, 480), samples=8 if PREVIEW else 12, exposure=-0.3)
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
    frames = [sec(x) for x in (0, 3, 11, 13.5, 16, 19)] if '--last' not in sys.argv else [sec(19)]
else:
    frames = list(range(sec(0), sec(9), 6)) + list(range(sec(9), sec(22) + 1, 2))
track = {}
for f in frames:
    sc.frame_set(f)
    track[f] = {"creature": rig.head_box(c, cam), "man": rig.head_box(man, cam)}
    sc.render.filepath = str(out / f"{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("frame", f, flush=True)
rig.write_json(out / ("track_preview.json" if PREVIEW else "track.json"), track)
