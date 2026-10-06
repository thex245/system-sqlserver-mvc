"""SLIDE 04 — P-04 containment room, CCTV footage.

Timeline (scene runs at 30 fps, rendered every 2nd frame = 15 fps CCTV):
  0-6 s    specimen sits on the floor hugging its knees, completely still
  6-7.5 s  door opens, corridor light spills in
  6.3-10 s employee walks in and stops in front of it
  9-13 s   the specimen slowly raises its head
  14-17 s  it extends its hand
  17-18 s  the employee hesitates (half step back)
  19-22 s  it begins to smile; the ceiling light stutters

Outputs build/renders/containment/{cam1,cam2}/####.png and track.json
(screen-space head boxes, used by the compositor for the "enhance" zoom).

usage: python3 scene_containment.py [--preview] [--cam cam1|cam2] [--frames a b]
"""
import argparse
import math
import sys

import bpy
from mathutils import Vector

import cast
import rig
from rig import v

ap = argparse.ArgumentParser()
ap.add_argument("--preview", action="store_true")
ap.add_argument("--cam", default="cam1")
ap.add_argument("--frames", type=int, nargs=2, default=None)
ap.add_argument("--step", type=int, default=2)
ap.add_argument("--samples", type=int, default=12)
ap.add_argument("--res", type=int, nargs=2, default=(640, 480))
ap.add_argument("--track-only", action="store_true")
args = ap.parse_args(sys.argv[1:])

rig.reset_scene()
sc = bpy.context.scene
sc.render.fps = 30          # set before importing so actions map to real seconds
FPS = 30


def sec(t):
    return int(round(t * FPS)) + 1


# ---------------------------------------------------------------- room
RX, RY, RZ = 2.0, 2.25, 3.0          # half-width, half-depth, height
DOOR_Y, DOOR_W, DOOR_H = -1.0, 1.0, 2.15
wall_tiles_x = rig.tile_material("tiles_x", tile=(0.46, 0.50, 0.45), grout=(0.16, 0.17, 0.15),
                                 scale=3.4, dirt=0.85, axes=("X", "Z"))
wall_tiles_y = rig.tile_material("tiles_y", tile=(0.46, 0.50, 0.45), grout=(0.16, 0.17, 0.15),
                                 scale=3.4, dirt=0.85, axes=("Y", "Z"))
concrete = rig.noise_material("concrete", (0.09, 0.09, 0.085), (0.24, 0.24, 0.22), scale=9, rough=0.7, bump=0.2,
                              distortion=0.6)
ceiling_mat = rig.noise_material("ceiling", (0.45, 0.46, 0.45), (0.55, 0.56, 0.55), scale=6, rough=0.9, bump=0.05)
steel = rig.noise_material("steel", (0.22, 0.24, 0.25), (0.30, 0.32, 0.33), scale=30, rough=0.45, bump=0.05)
glass = rig.principled("glass_dark", (0.02, 0.025, 0.03), rough=0.08, spec=0.9)

t = 0.1
rig.box("floor", (2 * RX, 2 * RY, t), (0, 0, -t / 2), concrete)
rig.box("ceiling", (2 * RX, 2 * RY, t), (0, 0, RZ + t / 2), ceiling_mat)
rig.box("wall_back", (2 * RX, t, RZ), (0, RY + t / 2, RZ / 2), wall_tiles_x)
rig.box("wall_front", (2 * RX, t, RZ), (0, -RY - t / 2, RZ / 2), wall_tiles_x)
rig.box("wall_right", (t, 2 * RY, RZ), (RX + t / 2, 0, RZ / 2), wall_tiles_y)
# left wall with a door opening
y0, y1 = DOOR_Y - DOOR_W / 2, DOOR_Y + DOOR_W / 2
rig.box("wall_left_a", (t, y0 + RY, RZ), (-RX - t / 2, (-RY + y0) / 2, RZ / 2), wall_tiles_y)
rig.box("wall_left_b", (t, RY - y1, RZ), (-RX - t / 2, (y1 + RY) / 2, RZ / 2), wall_tiles_y)
rig.box("wall_left_c", (t, DOOR_W, RZ - DOOR_H), (-RX - t / 2, DOOR_Y, (RZ + DOOR_H) / 2), wall_tiles_y)
# floor drain
bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.01, location=(0.15, 0.2, 0.002))
drain = bpy.context.active_object
drain.data.materials.append(rig.principled("drain", (0.02, 0.02, 0.02), rough=0.6))
# corridor outside the door
rig.box("corridor_floor", (3, 3, t), (-RX - 1.5, DOOR_Y, -t / 2), concrete)
rig.box("corridor_wall", (t, 3, RZ), (-RX - 1.6, DOOR_Y, RZ / 2), wall_tiles_y)

# door (hinged at the y0 edge, opens into the room)
hinge = bpy.data.objects.new("door_hinge", None)
sc.collection.objects.link(hinge)
hinge.location = (-RX, y1 - 0.02, 0)
door = rig.box("door", (0.06, DOOR_W - 0.04, DOOR_H - 0.02), (-RX, DOOR_Y, DOOR_H / 2), steel)
win = rig.box("door_window", (0.07, 0.22, 0.32), (-RX, DOOR_Y + 0.12, 1.55), glass)
for o in (door, win):
    o.parent = hinge
    o.matrix_parent_inverse = hinge.matrix_world.inverted()
hinge.rotation_euler = (0, 0, 0)
hinge.keyframe_insert("rotation_euler", frame=sec(6.0))
hinge.rotation_euler = (0, 0, math.radians(100))
hinge.keyframe_insert("rotation_euler", frame=sec(7.6))

# ceiling fixture + lights
fixture = rig.box("fixture", (1.25, 0.3, 0.05), (0.1, 0.35, RZ - 0.03),
                  rig.principled("tube", (1, 1, 1), emission=((0.86, 1.0, 0.88), 9.0)))
lamp = rig.area_light("fluoro", (0.1, 0.35, RZ - 0.08), (0, 0, 0), 1.2, 210, color=(0.88, 1.0, 0.9), size_y=0.28)
rig.area_light("bounce", (0, 0, 0.3), (math.radians(180), 0, 0), 3.0, 18, color=(0.9, 1, 0.92))
rig.area_light("corridor", (-RX - 1.2, DOOR_Y, 2.7), (0, 0, 0), 1.2, 260, color=(1.0, 0.95, 0.85))
# the light stutters while it smiles
for f, e in [(sec(20.6), 210), (sec(20.7), 25), (sec(20.8), 210), (sec(21.6), 210), (sec(21.67), 6),
             (sec(21.8), 190), (sec(21.85), 40), (sec(22.0), 210)]:
    lamp.data.energy = e
    lamp.data.keyframe_insert("energy", frame=f)
    fixture.active_material.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 9 * e / 210
    fixture.active_material.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].keyframe_insert(
        "default_value", frame=f)
rig.world((0.0, 0.0, 0.0), 0.0)

# ---------------------------------------------------------------- creature
C_POS = Vector((0.35, 0.6, 0.0))
c = cast.make_creature("p04")
cast.add_smile(c)
c.root.location = C_POS
c.root.rotation_euler = (0, 0, math.radians(-30))  # body angled between the camera and the door

E_STOP = Vector((-0.85, -0.25, 0.0))
E_HEAD = E_STOP + Vector((0, 0, 1.68))


def to_char(c, world_dir):
    return (c.root.matrix_world.to_3x3().inverted() @ Vector(world_dir)).normalized()


bpy.context.view_layer.update()
c_head = C_POS + Vector((0, 0, 0.78))
look_emp = to_char(c, E_HEAD - c_head)
reach_dir = to_char(c, (E_STOP + Vector((0, 0, 1.05))) - (C_POS + Vector((-0.15, 0, 0.95))))
look_emp_t = tuple(look_emp)
HUG = cast.SIT_HUG
LOOK = cast.sit_look(look_emp_t, neck=(0, -0.35, 1))
REACH = cast.sit_reach(look_emp_t, tuple(reach_dir))
CAM_POS = Vector((1.85, -2.05, 2.7))
look_cam = to_char(c, CAM_POS - c_head)
REACH_CAM = cast.sit_reach(tuple(look_cam), tuple(reach_dir))
REACH_CAM["Neck"] = v(*to_char(c, (CAM_POS - c_head).normalized() * 0.4 + Vector((0, 0, 1))))

c.key_pose(sec(0), HUG, hips=cast.SIT_HIPS)
c.key_pose(sec(9.0), HUG, hips=cast.SIT_HIPS)
c.key_pose(sec(13.0), LOOK, hips=cast.SIT_HIPS)
c.key_pose(sec(14.0), LOOK, hips=cast.SIT_HIPS)
c.key_pose(sec(17.0), REACH, hips=cast.SIT_HIPS)
c.key_pose(sec(20.8), REACH, hips=cast.SIT_HIPS)
c.key_pose(sec(22.2), REACH_CAM, hips=cast.SIT_HIPS)     # turns to look straight into the camera
c.key_pose(sec(24.0), REACH_CAM, hips=cast.SIT_HIPS)
cast.key_smile(c, sec(0), 0.0)
cast.key_smile(c, sec(18.4), 0.0)
cast.key_smile(c, sec(20.4), 0.5)     # a thin line splits the blank face
cast.key_smile(c, sec(22.2), 1.0)     # opens while it turns to the camera

# ---------------------------------------------------------------- employee
e = cast.make_employee("emp")
walk = next(a for a in bpy.data.actions if a.name.startswith("Walk"))
idle = next(a for a in bpy.data.actions if a.name.startswith("Idle"))
# measure walking speed of the in-place cycle from the planted foot
e.arm.animation_data.action = walk
f0, f1 = walk.frame_range
ys = []
for f in range(int(f0), int(f1) + 1):
    sc.frame_set(f)
    ys.append(e.joint("LeftFoot").y)
cycle = (f1 - f0) / FPS
speed = 2 * (max(ys) - min(ys)) / cycle * 0.92
e.arm.animation_data.action = None
print("walk cycle", round(cycle, 3), "s  speed", round(speed, 3), "m/s")

path = [Vector((-RX - 1.0, DOOR_Y, 0)), Vector((-RX + 0.5, DOOR_Y + 0.05, 0)), E_STOP]
t_start = 6.4
t = t_start
keys = []
for a, b in zip(path, path[1:]):
    keys.append((t, a, b - a))
    t += (b - a).length / speed
t_arrive = t
e.root.location = path[0]
for (tt, p, d) in keys:
    e.root.location = p
    e.root.rotation_euler = (0, 0, math.atan2(d.x, -d.y))
    e.root.keyframe_insert("location", frame=sec(tt))
    e.root.keyframe_insert("rotation_euler", frame=sec(tt))
face_c = C_POS - E_STOP
yaw_c = math.atan2(face_c.x, -face_c.y)
e.root.location = E_STOP
e.root.rotation_euler = (0, 0, math.atan2(keys[-1][2].x, -keys[-1][2].y))
e.root.keyframe_insert("location", frame=sec(t_arrive))
e.root.keyframe_insert("rotation_euler", frame=sec(t_arrive))
e.root.rotation_euler = (0, 0, yaw_c)
e.root.keyframe_insert("rotation_euler", frame=sec(t_arrive + 0.7))
e.root.keyframe_insert("location", frame=sec(17.0))
e.root.keyframe_insert("rotation_euler", frame=sec(17.0))
back = -face_c.normalized() * 0.16
e.root.location = E_STOP + back
e.root.rotation_euler = (0, 0, yaw_c + math.radians(-9))
e.root.keyframe_insert("location", frame=sec(17.7))
e.root.keyframe_insert("rotation_euler", frame=sec(17.7))
rig.set_interpolation(e.root, "LINEAR")
ad = e.arm.animation_data
tr_walk = ad.nla_tracks.new()
st = tr_walk.strips.new("walk", sec(t_start), walk)
st.repeat = max(1.0, (t_arrive - t_start + 0.3) / cycle)
st.extrapolation = "NOTHING"
tr_idle = ad.nla_tracks.new()
st2 = tr_idle.strips.new("idle", sec(t_arrive - 0.15), idle)
st2.repeat = 6
st2.blend_in = 10
st2.extrapolation = "HOLD_FORWARD"
# the employee stays out of shot (behind the wall) until the door opens
e.root.hide_render = False

# ---------------------------------------------------------------- cameras
cam1 = rig.camera("cam1", tuple(CAM_POS), (-0.75, 0.55, 0.45), lens=17)
bpy.context.view_layer.update()
sc.frame_set(sec(22.4))
end_head = (c.joint("Head") + c.joint("HeadTop_End")) / 2
cam2 = rig.camera("cam2", tuple(CAM_POS), tuple(end_head + Vector((0, 0, -0.02))), lens=125)
sc.camera = cam1 if args.cam == "cam1" else cam2

rs = rig.render_settings(res=tuple(args.res), samples=8 if args.preview else args.samples, exposure=-0.45)
out = rig.out_dir("containment")
cam = sc.camera
sub = out / args.cam
sub.mkdir(exist_ok=True)

a, b = args.frames if args.frames else (sec(0), sec(24.0))
if args.preview:
    frames = [sec(x) for x in (3, 8.5, 11, 13.5, 17.5, 20.5, 22.5)]
else:
    frames = list(range(a, b + 1, args.step))

track = {}
for f in frames:
    sc.frame_set(f)
    track[f] = {"creature": rig.head_box(c, cam), "employee": rig.head_box(e, cam)}
    if args.track_only:
        continue
    sc.render.filepath = str(sub / f"{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("frame", f, flush=True)
rig.write_json(sub / ("track_preview.json" if args.preview else f"track_{a}_{b}.json"), track)
