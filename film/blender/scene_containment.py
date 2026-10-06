"""SLIDE 04 — P-04 containment room, CCTV footage at 60 fps.

Choreography (times in film/p04.py):
  the specimen sits on the floor hugging its knees, completely still;
  the door latch rattles, the door swings open, an employee in protective gear
  appears, stops in the doorway, then approaches slowly and kneels at its eye level;
  it raises its head in stages and extends its hand, elbow first; he reaches back,
  stops short, holds, and pulls his hand away. Three minutes later (clock jump in
  the edit) a thin line opens across its blank face. The light flickers and dies.
  When it comes back the specimen is looking straight into the camera, grinning.

Cameras: cam1 = the CCTV; z4 / z8 = the same camera with 4x / 8x focal length and
lens shift onto its face (an exact optical stand-in for a digital zoom).

Outputs build/renders/p04/<cam>/#####.png and track.json
usage: python3 scene_containment.py [--cam cam1|z4|z8] [--frames a b] [--sheet t1 t2 ...] [--lowres]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cast  # noqa: E402
import p04  # noqa: E402
import rig  # noqa: E402
from p04 import frame as fr  # noqa: E402
from rig import v  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--cam", default="cam1")
ap.add_argument("--frames", type=int, nargs=2, default=None)
ap.add_argument("--sheet", type=float, nargs="+", default=None)
ap.add_argument("--lowres", action="store_true")
ap.add_argument("--samples", type=int, default=6)
ap.add_argument("--res", type=int, nargs=2, default=(512, 384))
ap.add_argument("--track-only", action="store_true")
args = ap.parse_args(sys.argv[1:])

rig.reset_scene()
sc = bpy.context.scene
sc.render.fps = p04.FPS          # before importing, so actions map to real seconds

# ---------------------------------------------------------------- room
RX, RY, RZ = 2.0, 2.25, 3.0
DOOR_Y, DOOR_W, DOOR_H = -1.0, 1.0, 2.15
wall_x = rig.tile_material("tiles_x", tile=(0.46, 0.50, 0.45), grout=(0.16, 0.17, 0.15), scale=3.4, dirt=0.85,
                           axes=("X", "Z"))
wall_y = rig.tile_material("tiles_y", tile=(0.46, 0.50, 0.45), grout=(0.16, 0.17, 0.15), scale=3.4, dirt=0.85,
                           axes=("Y", "Z"))
concrete = rig.noise_material("concrete", (0.09, 0.09, 0.085), (0.24, 0.24, 0.22), scale=9, rough=0.7, bump=0.2,
                              distortion=0.6)
ceiling_m = rig.noise_material("ceiling", (0.45, 0.46, 0.45), (0.55, 0.56, 0.55), scale=6, rough=0.9, bump=0.05)
steel = rig.noise_material("steel", (0.22, 0.24, 0.25), (0.30, 0.32, 0.33), scale=30, rough=0.45, bump=0.05)
glass = rig.principled("glass_dark", (0.02, 0.025, 0.03), rough=0.08, spec=0.9)
dark_metal = rig.principled("handle", (0.05, 0.05, 0.05), rough=0.3, metallic=0.8)
t = 0.1
rig.box("floor", (2 * RX, 2 * RY, t), (0, 0, -t / 2), concrete)
rig.box("ceiling", (2 * RX, 2 * RY, t), (0, 0, RZ + t / 2), ceiling_m)
rig.box("wall_back", (2 * RX, t, RZ), (0, RY + t / 2, RZ / 2), wall_x)
rig.box("wall_front", (2 * RX, t, RZ), (0, -RY - t / 2, RZ / 2), wall_x)
rig.box("wall_right", (t, 2 * RY, RZ), (RX + t / 2, 0, RZ / 2), wall_y)
y0, y1 = DOOR_Y - DOOR_W / 2, DOOR_Y + DOOR_W / 2
rig.box("wall_left_a", (t, y0 + RY, RZ), (-RX - t / 2, (-RY + y0) / 2, RZ / 2), wall_y)
rig.box("wall_left_b", (t, RY - y1, RZ), (-RX - t / 2, (y1 + RY) / 2, RZ / 2), wall_y)
rig.box("wall_left_c", (t, DOOR_W, RZ - DOOR_H), (-RX - t / 2, DOOR_Y, (RZ + DOOR_H) / 2), wall_y)
bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.01, location=(0.15, 0.2, 0.002))
bpy.context.active_object.data.materials.append(rig.principled("drain", (0.02, 0.02, 0.02), rough=0.6))
rig.box("corridor_floor", (3, 3, t), (-RX - 1.5, DOOR_Y, -t / 2), concrete)
rig.box("corridor_wall", (t, 3, RZ), (-RX - 1.6, DOOR_Y, RZ / 2), wall_y)

# door: hinged on its far edge, opens into the room toward the back wall
hinge = bpy.data.objects.new("door_hinge", None)
sc.collection.objects.link(hinge)
hinge.location = (-RX, y1 - 0.02, 0)
door_parts = [rig.box("door", (0.06, DOOR_W - 0.04, DOOR_H - 0.02), (-RX, DOOR_Y, DOOR_H / 2), steel),
              rig.box("door_window", (0.07, 0.22, 0.32), (-RX, DOOR_Y + 0.12, 1.55), glass),
              rig.box("handle_in", (0.06, 0.14, 0.025), (-RX + 0.06, DOOR_Y - 0.33, 1.02), dark_metal),
              rig.box("plate_in", (0.012, 0.05, 0.16), (-RX + 0.035, DOOR_Y - 0.38, 1.02), dark_metal)]
for o in door_parts:
    o.parent = hinge
    o.matrix_parent_inverse = hinge.matrix_world.inverted()
for tt, ang in [(0, 0), (p04.LATCH, 0), (p04.LATCH + 0.07, 1.6), (p04.LATCH + 0.15, -0.6), (p04.LATCH + 0.24, 1.0),
                (p04.LATCH + 0.34, 0), (p04.DOOR_OPEN[0], 0), (p04.DOOR_OPEN[0] + 0.35, 14),
                (p04.DOOR_OPEN[1], 100)]:
    hinge.rotation_euler = (0, 0, math.radians(ang))
    hinge.keyframe_insert("rotation_euler", frame=fr(tt))

# lights
fixture_mat = rig.principled("tube", (1, 1, 1), emission=((0.86, 1.0, 0.88), 9.0))
rig.box("fixture", (1.25, 0.3, 0.05), (0.1, 0.35, RZ - 0.03), fixture_mat)
lamp = rig.area_light("fluoro", (0.1, 0.35, RZ - 0.08), (0, 0, 0), 1.2, 210, color=(0.88, 1.0, 0.9), size_y=0.28)
bounce = rig.area_light("bounce", (0, 0, 0.3), (math.radians(180), 0, 0), 3.0, 18, color=(0.9, 1, 0.92))
corridor = rig.area_light("corridor", (-RX - 1.2, DOOR_Y, 2.7), (0, 0, 0), 1.2, 260, color=(1.0, 0.95, 0.85))
emis = fixture_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]


def light_state(tt, k):
    """k = 1 normal, 0 dead"""
    lamp.data.energy = 210 * k
    lamp.data.keyframe_insert("energy", frame=fr(tt))
    bounce.data.energy = 18 * k
    bounce.data.keyframe_insert("energy", frame=fr(tt))
    corridor.data.energy = 260 * (0.06 + 0.94 * k)
    corridor.data.keyframe_insert("energy", frame=fr(tt))
    emis.default_value = 9.0 * k
    emis.keyframe_insert("default_value", frame=fr(tt))


light_state(0, 1)
for a, b in p04.FLICKERS:
    light_state(a, 0.08)
    light_state(b, 1)
light_state(p04.BLACKOUT[0], 0)
light_state(p04.BLACKOUT[1], 1)
light_state(p04.BLACKOUT[1] + 0.06, 0.15)
light_state(p04.BLACKOUT[1] + 0.11, 1)
for idb in (lamp.data, bounce.data, corridor.data, fixture_mat.node_tree):
    rig.constant_interp(idb)
rig.world((0, 0, 0), 0)

# ---------------------------------------------------------------- positions
CAM_POS = Vector((1.85, -2.05, 2.7))
C_POS = Vector((0.35, 0.6, 0.0))
TO_EMP = Vector((-0.78, -0.62, 0)).normalized()
E_KNEEL = C_POS + TO_EMP * 1.02                    # where he kneels, ~1 m from it
E_P0 = Vector((-RX - 1.3, DOOR_Y, 0))              # out in the corridor
E_P1 = Vector((-RX + 0.3, DOOR_Y + 0.05, 0))       # just inside the door


def yaw_to(d):
    return math.atan2(d.x, -d.y)


def to_char(ch, d):
    return tuple((ch.root.matrix_world.to_3x3().inverted() @ Vector(d)).normalized())


# ---------------------------------------------------------------- the specimen
c = cast.make_creature("p04")
cast.add_smile(c)
c.root.location = C_POS
c.root.rotation_euler = (0, 0, yaw_to(TO_EMP))     # its body faces him; the camera sees it in profile
bpy.context.view_layer.update()

C_HEAD = C_POS + Vector((0, 0, 0.8))
E_HEAD_KNEEL = E_KNEEL + Vector((0, 0, 1.18))
look_floor = to_char(c, (E_KNEEL + Vector((0, 0, 0.1))) - C_HEAD)
look_emp = to_char(c, E_HEAD_KNEEL - C_HEAD)
look_cam = to_char(c, CAM_POS - C_HEAD)
look_past = to_char(c, CAM_POS + Vector((0.9, 0.4, 0)) - C_HEAD)

HUG = cast.SIT_HUG
HALF = dict(cast.LEGS_SIT, **cast.HUG_ARMS, **{
    "Spine": v(0, -0.3, 1), "Spine1": v(0, -0.42, 1), "Spine2": v(0, -0.46, 1), "Neck": v(0, -0.65, 0.75),
    "look": v(*look_floor), "fingers": 0.5})
LOOK = cast.sit_look(look_emp, neck=(0, -0.35, 1))


def reach_pose(look, hand_target, roll=0.0, neck=(0, -0.35, 1)):
    p = cast.sit_look(look, neck=neck)
    p["roll"] = roll
    c.pose(p, hips=cast.SIT_HIPS)
    if hand_target is not None:
        c.ik_arm("Right", hand_target, pole=Vector((0, 0, -1)) - Vector(TO_EMP) * 0.2,
                 hand_dir=(Vector(hand_target) - c.joint("RightForeArm")).normalized() + Vector((0, 0, 0.15)))
        c.curl_fingers(0.12, side=("Right",))


# hand targets (world): elbow leads, then the forearm unfolds toward him
c.pose(LOOK, hips=cast.SIT_HIPS)
sh = c.joint("RightArm")
HAND_FINAL = sh + (E_KNEEL + Vector((0, 0, 0.78)) - sh).normalized() * 0.86
HAND_MID = sh + (HAND_FINAL - sh) * 0.55 + Vector((0, 0, -0.12))
HAND_LOW = sh + Vector(TO_EMP) * 0.22 + Vector((0, 0, -0.32))


def ckey(tt, pose=None, hand=None, look=None, roll=0.0, neck=(0, -0.35, 1)):
    if pose is not None:
        c.pose(pose, hips=cast.SIT_HIPS)
    else:
        reach_pose(look, hand, roll, neck)
    c.key(fr(tt))


ckey(0, HUG)
ckey(p04.HEAD_UP[0], HUG)
ckey(p04.HEAD_UP[0] + 1.3, HALF)
ckey(p04.HEAD_UP[1], LOOK)
ckey(p04.HAND_OUT[0], LOOK)
ckey(p04.HAND_OUT[0] + 1.2, look=look_emp, hand=HAND_LOW)
ckey(p04.HAND_OUT[0] + 2.3, look=look_emp, hand=HAND_MID)
ckey(p04.HAND_OUT[1], look=look_emp, hand=HAND_FINAL)
ckey(p04.BLACKOUT[0] + 0.02, look=look_emp, hand=HAND_FINAL)
# the turn happens in the dark: fast, with an overshoot
ckey(p04.BLACKOUT[0] + 0.10, look=look_past, hand=HAND_FINAL, neck=(0.1, -0.2, 1))
ckey(p04.BLACKOUT[0] + 0.16, look=look_cam, hand=HAND_FINAL, roll=-14, neck=(0.12, -0.25, 1))
ckey(p04.STARE, look=look_cam, hand=HAND_FINAL, roll=-14, neck=(0.12, -0.25, 1))
# while it stares, its head keeps tilting, very slowly
ckey(p04.FREEZE, look=look_cam, hand=HAND_FINAL, roll=-27, neck=(0.12, -0.25, 1))
ckey(p04.FREEZE + 2, look=look_cam, hand=HAND_FINAL, roll=-27, neck=(0.12, -0.25, 1))
cast.key_smile(c, fr(0), 0.0)
cast.key_smile(c, fr(p04.SMILE[0]), 0.0)
cast.key_smile(c, fr(p04.SMILE[1]), 0.5)
cast.key_smile(c, fr(p04.BLACKOUT[0] + 0.05), 0.5)
cast.key_smile(c, fr(p04.BLACKOUT[0] + 0.2), 1.0)

# ---------------------------------------------------------------- the employee
e = cast.make_employee("emp")
walk = next(a for a in bpy.data.actions if a.name.startswith("Walk"))
idle = next(a for a in bpy.data.actions if a.name.startswith("Idle"))
e.arm.animation_data.action = walk
f0, f1 = walk.frame_range
ys = []
for f in range(int(f0), int(f1) + 1):
    sc.frame_set(f)
    ys.append(e.joint("LeftFoot").y)
cycle_s = (f1 - f0) / p04.FPS
natural_speed = 2 * (max(ys) - min(ys)) / cycle_s * 0.92
e.arm.animation_data.action = None
print(f"walk cycle {cycle_s:.3f}s natural speed {natural_speed:.2f} m/s")

ad = e.arm.animation_data
tr_idle = ad.nla_tracks.new()
tr_idle.name = "idle"
st = tr_idle.strips.new("idle", fr(p04.WALK1[0] - 1), idle)
st.repeat = 40
st.extrapolation = "HOLD"
tr_walk = ad.nla_tracks.new()
tr_walk.name = "walk"


def walk_segment(t0, t1, a, b):
    speed = (b - a).length / (t1 - t0)
    s = tr_walk.strips.new(f"walk{t0}", fr(t0), walk)
    s.scale = natural_speed / speed
    s.repeat = max(1.0, (t1 - t0 + 0.1) / (cycle_s * s.scale))
    s.blend_in = 6
    s.blend_out = 10
    s.extrapolation = "NOTHING"
    for tt, p in ((t0, a), (t1, b)):
        e.root.location = p
        e.root.keyframe_insert("location", frame=fr(tt))
    return speed


def face(tt, d):
    e.root.rotation_euler = (0, 0, yaw_to(d))
    e.root.keyframe_insert("rotation_euler", frame=fr(tt))


e.root.location = E_P0
e.root.keyframe_insert("location", frame=fr(0))
face(0, E_P1 - E_P0)
s1 = walk_segment(*p04.WALK1, E_P0, E_P1)
face(p04.WALK1[1] - 0.2, E_P1 - E_P0)
face(p04.PAUSE[0] + 0.5, C_POS - E_P1)                # turns to look at it from the doorway
face(p04.WALK2[0], E_KNEEL - E_P1)
s2 = walk_segment(*p04.WALK2, E_P1, E_KNEEL)
face(p04.WALK2[1] - 0.3, E_KNEEL - E_P1)
face(p04.WALK2[1] + 0.5, C_POS - E_KNEEL)
print(f"walk speeds {s1:.2f} / {s2:.2f} m/s")

# kneel / reach / hesitate: keyed poses in their own action, faded in over the idle
KNEEL = {"LeftUpLeg": v(0.12, -1, -0.05), "LeftLeg": v(0.02, 0.12, -1), "LeftFoot": v(0, -1, -0.1),
         "RightUpLeg": v(-0.1, 0.2, -1), "RightLeg": v(-0.02, 1, -0.12), "RightFoot": v(0, 1, -0.7),
         "Spine": v(0, -0.22, 1), "Spine1": v(0, -0.28, 1), "Spine2": v(0, -0.28, 1), "Neck": v(0, -0.3, 1),
         "LeftArm": v(0.2, -0.55, -1), "LeftForeArm": v(-0.15, -1, -0.15), "LeftHand": v(-0.1, -1, -0.3),
         "RightArm": v(-0.18, -0.25, -1), "RightForeArm": v(-0.05, -0.7, -0.75), "RightHand": v(0, -0.5, -1),
         "fingers": 0.3}
K_HIPS = (0, 0.12, -0.46)
e.root.location = E_KNEEL
e.root.rotation_euler = (0, 0, yaw_to(C_POS - E_KNEEL))
bpy.context.view_layer.update()
e_look = to_char(e, (C_HEAD + Vector((0, 0, -0.05))) - E_HEAD_KNEEL)
kneel_act = bpy.data.actions.new("kneel")
ad.action = kneel_act


def ekey(tt, hand=None, spine=None, look=e_look, fingers=0.3):
    p = dict(KNEEL, look=v(*look), fingers=fingers)
    if spine:
        p["Spine1"] = v(*spine)
    e.pose(p, hips=K_HIPS)
    if hand is not None:
        e.ik_arm("Right", hand, pole=Vector((0, 0, -1)) - Vector(TO_EMP) * 0.3,
                 hand_dir=(Vector(hand) - e.joint("RightForeArm")).normalized())
    e.key(fr(tt))


e.pose(dict(KNEEL, look=v(*e_look)), hips=K_HIPS)
e_sh = e.joint("RightArm")
GAP = HAND_FINAL + (e_sh - HAND_FINAL).normalized() * 0.2       # stops 20 cm short of its hand
HALFWAY = e_sh + (GAP - e_sh) * 0.45 + Vector((0, 0, -0.08))
BACK = e_sh + (GAP - e_sh) * 0.3 + Vector((0, 0, -0.18))
ekey(p04.KNEEL[0])
ekey(p04.REACH[0])
ekey(p04.REACH[0] + 0.5, hand=HALFWAY, fingers=0.15)
ekey(p04.REACH[1], hand=GAP, fingers=0.05)
ekey(p04.HOLD[1], hand=GAP, fingers=0.12)
ekey(p04.RETRACT[1], hand=BACK, spine=(0, -0.05, 1), fingers=0.45)
ekey(p04.SKIP - 0.02, hand=BACK, spine=(0, -0.05, 1), fingers=0.45)
ekey(p04.SKIP + 0.02)                                 # three minutes later: hand resting again
ekey(p04.FREEZE + 2)
ad.action = None
tr_k = ad.nla_tracks.new()
tr_k.name = "kneel"
ks = tr_k.strips.new("kneel", fr(p04.KNEEL[0]), kneel_act)
ks.extrapolation = "HOLD_FORWARD"
ks.use_animated_influence = True
ks.influence = 0.0
ks.keyframe_insert("influence", frame=fr(p04.KNEEL[0]))
ks.influence = 1.0
ks.keyframe_insert("influence", frame=fr(p04.KNEEL[1]))
# the root stays put while kneeling
e.root.location = E_KNEEL
e.root.keyframe_insert("location", frame=fr(p04.FREEZE + 2))
rig.set_interpolation(e.root, "LINEAR")

# ---------------------------------------------------------------- cameras
cam1 = rig.camera("cam1", tuple(CAM_POS), (-0.75, 0.55, 0.45), lens=17)
bpy.context.view_layer.update()
sc.camera = cam1
rs = rig.render_settings(res=(320, 240) if args.lowres else tuple(args.res),
                         samples=4 if args.lowres else args.samples, exposure=-0.45)
sc.cycles.use_fast_gi = True
sc.cycles.diffuse_bounces = 2
sc.cycles.glossy_bounces = 1
sc.cycles.transmission_bounces = 1
sc.cycles.transparent_max_bounces = 2

sc.frame_set(fr(p04.ZOOM8))
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
hc = c.joint("Head") * 0.42 + c.joint("HeadTop_End") * 0.58
uv = world_to_camera_view(sc, cam1, hc)
zoom_info = {}
for name, k in (("z4", p04.ZOOM4_LENS_FACTOR), ("z8", p04.ZOOM8_LENS_FACTOR)):
    z = rig.camera(name, tuple(CAM_POS), (-0.75, 0.55, 0.45), lens=17 * k)
    z.data.shift_x = (uv.x - 0.5) * k
    z.data.shift_y = (uv.y - 0.5) * k * 3 / 4
    zoom_info[name] = dict(k=k, center=[uv.x, 1 - uv.y])
sc.camera = bpy.data.objects[args.cam]
cam = sc.camera

out = rig.out_dir("p04")
sub = out / ("sheet" if args.sheet else args.cam)
sub.mkdir(exist_ok=True)
rig.write_json(out / "zoom.json", zoom_info)

if args.sheet:
    frames = [fr(x) for x in args.sheet]
elif args.frames:
    frames = list(range(args.frames[0], args.frames[1] + 1))
else:
    rng = {"cam1": [fr(0)] + list(range(fr(p04.STATIC_END), fr(p04.ZOOM4) + 1)),
           "z4": list(range(fr(p04.ZOOM4), fr(p04.ZOOM8) + 1)),
           "z8": list(range(fr(p04.ZOOM8), fr(p04.FREEZE) + 1))}
    frames = rng[args.cam]

track = {}
for f in frames:
    sc.frame_set(f)
    track[f] = {"creature": rig.head_box(c, cam), "employee": rig.head_box(e, cam)}
    if args.track_only:
        continue
    sc.render.filepath = str(sub / f"{f:05d}.png")
    bpy.ops.render.render(write_still=True)
    print("frame", f, flush=True)
if not args.sheet:
    tp = sub / "track.json"
    old = json.loads(tp.read_text()) if tp.exists() else {}
    old.update({str(k): val for k, val in track.items()})
    tp.write_text(json.dumps(old))
