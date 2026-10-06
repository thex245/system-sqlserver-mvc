"""Single-frame Blender photographs.

  forest        SLIDE 01  night flash photo: a pale figure standing deep among the trees
  corridor      SLIDE 07  empty laboratory corridor
  corridor_end  SLIDE 08  same corridor, far lights dead, a silhouette at the end
  hallway_her   SLIDE 10  a home hallway at night, someone familiar standing in the doorway
  hallway_it    SLIDE 10  the same frame, but it is the specimen (used for single-frame flashes)

usage: python3 scene_stills.py <name> [--preview]
"""
import math
import random
import sys

import bpy
from mathutils import Vector

import cast
import rig
from rig import v

name = sys.argv[1]
PREVIEW = "--preview" in sys.argv
out = rig.out_dir("stills")
track = {}


def finish(cam, res, samples, exposure=0.0, look="AgX - Medium High Contrast", heads=()):
    sc = rig.render_settings(res=res, samples=12 if PREVIEW else samples, exposure=exposure, look=look)
    sc.camera = cam
    for key, ch in heads:
        track[key] = rig.head_box(ch, cam)
    sc.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    rig.write_json(out / f"{name}.json", track)


def creature_at(loc, yaw_deg, pose=None, smile=None):
    c = cast.make_creature("pasion")
    if smile is not None:
        cast.add_smile(c)
    c.root.location = loc
    c.root.rotation_euler = (0, 0, math.radians(yaw_deg))
    bpy.context.view_layer.update()
    c.pose(pose or cast.STAND)
    if smile is not None:
        cast.set_smile(c, smile)
    return c


# ------------------------------------------------------------------ forest
def forest():
    random.seed(7)
    sc = bpy.context.scene
    bark = rig.noise_material("bark", (0.012, 0.011, 0.01), (0.09, 0.08, 0.07), scale=3.0, rough=0.95, bump=0.9,
                              detail=10, distortion=1.5)
    # stretch the bark noise vertically
    nt = bark.node_tree
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6.0, 6.0, 0.6)
    nz = next(n for n in nt.nodes if n.type == "TEX_NOISE")
    tc = next(n for n in nt.nodes if n.type == "TEX_COORD")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    litter = rig.noise_material("litter", (0.02, 0.016, 0.012), (0.12, 0.09, 0.05), scale=40, rough=0.95, bump=0.8,
                                detail=12, distortion=2.0)
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 30, 0))
    ground = bpy.context.active_object
    ground.data.materials.append(litter)
    # ground undulation
    bpy.ops.object.modifier_add(type="SUBSURF")
    ground.modifiers[-1].subdivision_type = "SIMPLE"
    ground.modifiers[-1].levels = ground.modifiers[-1].render_levels = 6
    tex = bpy.data.textures.new("lumps", "CLOUDS")
    tex.noise_scale = 4.0
    disp = ground.modifiers.new("disp", "DISPLACE")
    disp.texture = tex
    disp.strength = 0.5
    # trunks
    fig_xy = Vector((0.15, 15.0))
    placed = []
    for i in range(420):
        x = random.uniform(-26, 26)
        y = random.uniform(2.5, 60)
        p = Vector((x, y))
        if (p - fig_xy).length < 1.1 or any((p - q).length < 1.3 for q in placed):
            continue
        if abs(x) < 1.0 and y < 7:   # keep a sight line open
            continue
        placed.append(p)
        r = random.uniform(0.09, 0.32)
        h = 18
        bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=r, depth=h, location=(x, y, h / 2 - 1.5))
        t = bpy.context.active_object
        t.rotation_euler = (random.uniform(-0.04, 0.04), random.uniform(-0.04, 0.04), random.uniform(0, 6.28))
        t.data.materials.append(bark)
    # the figure
    c = creature_at((fig_xy.x, fig_xy.y, 0.05), -4, dict(cast.STAND, look=v(-0.05, -1, 0.02)))
    # camera + flash
    cam = rig.camera("cam", (0.0, 0.0, 1.55), (0.25, 15.0, 1.25), lens=32)
    flash = rig.point_light("flash", (0.08, 0.05, 1.75), 5000, color=(1.0, 0.97, 0.92), radius=0.02, kind="SPOT",
                            spot=80)
    flash.rotation_euler = (math.radians(91), 0, math.radians(180))
    flash.rotation_euler = (Vector((0.25, 15.0, 1.2)) - flash.location).to_track_quat("-Z", "Y").to_euler()
    rig.world((0.0015, 0.002, 0.004), 1.0)
    moon = bpy.data.objects.new("moon", bpy.data.lights.new("moon", "SUN"))
    moon.data.energy = 0.035
    moon.data.color = (0.6, 0.7, 1.0)
    moon.rotation_euler = (math.radians(35), 0, math.radians(160))
    sc.collection.objects.link(moon)
    sc.cycles.volume_bounces = 1
    finish(cam, (1200, 900), 96, exposure=0.3, heads=[("creature", c)])


# ------------------------------------------------------------------ corridor
def corridor(dead_end_lights=False, figure=False):
    L, Wd, Hh = 32.0, 2.4, 2.7
    paint_lo = rig.noise_material("paint_lo", (0.22, 0.28, 0.24), (0.27, 0.33, 0.29), scale=6, rough=0.45, bump=0.03)
    paint_hi = rig.noise_material("paint_hi", (0.42, 0.42, 0.37), (0.62, 0.61, 0.55), scale=4, rough=0.6, bump=0.02,
                                 distortion=1.0)
    lino = rig.tile_material("lino", tile=(0.42, 0.40, 0.34), grout=(0.25, 0.24, 0.2), scale=1.6, dirt=0.4,
                             rough=0.18, axes=("X", "Y"))
    ceil = rig.noise_material("ceil", (0.5, 0.5, 0.48), (0.58, 0.58, 0.55), scale=3, rough=0.9, bump=0.02)
    door_m = rig.principled("door", (0.12, 0.13, 0.14), rough=0.4)
    frame_m = rig.principled("frame", (0.05, 0.05, 0.05), rough=0.5)
    rig.box("floor", (Wd, L, 0.1), (0, L / 2, -0.05), lino)
    rig.box("ceiling", (Wd, L, 0.1), (0, L / 2, Hh + 0.05), ceil)
    for sx in (-1, 1):
        rig.box(f"wall_lo{sx}", (0.1, L, 1.1), (sx * (Wd / 2 + 0.05), L / 2, 0.55), paint_lo)
        rig.box(f"wall_hi{sx}", (0.1, L, Hh - 1.1), (sx * (Wd / 2 + 0.05), L / 2, 1.1 + (Hh - 1.1) / 2), paint_hi)
        rig.box(f"rail{sx}", (0.04, L, 0.05), (sx * (Wd / 2 - 0.0), L / 2, 1.1), frame_m)
        for k in range(5):
            y = 4 + k * 6.2 + (1.5 if sx > 0 else 0)
            rig.box(f"door{sx}{k}", (0.06, 1.0, 2.1), (sx * (Wd / 2 + 0.01), y, 1.05), door_m)
            rig.box(f"dframe{sx}{k}", (0.07, 1.14, 2.2), (sx * (Wd / 2 + 0.02), y, 1.1), frame_m)
            rig.box(f"dwin{sx}{k}", (0.075, 0.25, 0.35), (sx * (Wd / 2 + 0.02), y, 1.55),
                    rig.principled("dwin", (0.01, 0.012, 0.014), rough=0.05))
    rig.box("end_wall", (Wd, 0.1, Hh), (0, L + 0.05, Hh / 2), paint_hi)
    rig.box("end_door_l", (0.58, 0.06, 2.1), (-0.3, L - 0.01, 1.05), door_m)
    rig.box("end_door_r", (0.58, 0.06, 2.1), (0.3, L - 0.01, 1.05), door_m)
    n = 10
    for k in range(n):
        y = 1.5 + k * (L - 2) / (n - 1)
        on = True
        dim = 1.0
        if dead_end_lights:
            on = k < 5 or k == n - 1
            dim = 1.0 if k < 5 else 0.55
        em = rig.principled(f"tube{k}", (1, 1, 1), emission=((0.9, 1.0, 0.92), 6.0 * dim if on else 0.0))
        rig.box(f"fix{k}", (0.35, 1.2, 0.04), (0, y, Hh - 0.02), em)
        if on:
            rig.area_light(f"fl{k}", (0, y, Hh - 0.06), (0, 0, 0), 0.3, 120 * dim, color=(0.9, 1.0, 0.92), size_y=1.2)
    heads = []
    if figure:
        c = creature_at((0.12, L - 1.6, 0), 0, dict(cast.STAND, look=v(0, -1, -0.05)))
        c.material(rig.principled("shadow", (0.01, 0.01, 0.01), rough=0.9))
        rig.area_light("backlight", (0, L - 0.6, 2.3), (math.radians(-60), 0, 0), 0.8, 160, color=(0.9, 1, 0.92))
        heads = [("creature", c)]
    rig.world((0.0, 0.0, 0.0), 0.0)
    cam = rig.camera("cam", (0.25, 0.4, 1.55), (0.0, L, 1.3), lens=26)
    finish(cam, (1200, 900), 64, exposure=-0.9, heads=heads)


# ------------------------------------------------------------------ hallway
def hallway(it=False):
    L, Wd, Hh = 6.0, 1.3, 2.6
    paper = bpy.data.materials.new("wallpaper")
    paper.use_nodes = True
    nt = paper.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 18
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.30, 0.22, 0.14, 1)
    ramp.color_ramp.elements[1].color = (0.46, 0.38, 0.26, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    wood = rig.noise_material("wood", (0.12, 0.06, 0.03), (0.3, 0.17, 0.08), scale=2.0, rough=0.35, bump=0.05,
                              detail=4, distortion=4)
    ceil = rig.principled("ceil", (0.6, 0.57, 0.5), rough=0.9)
    trim = rig.principled("trim", (0.75, 0.72, 0.64), rough=0.5)
    rig.box("floor", (Wd + 0.4, L + 4, 0.1), (0, L / 2 + 1.5, -0.05), wood)
    rig.box("ceiling", (Wd + 0.4, L + 4, 0.1), (0, L / 2 + 1.5, Hh + 0.05), ceil)
    for sx in (-1, 1):
        rig.box(f"wall{sx}", (0.1, L, Hh), (sx * (Wd / 2 + 0.05), L / 2, Hh / 2), paper)
        rig.box(f"skirt{sx}", (0.03, L, 0.14), (sx * (Wd / 2 - 0.01), L / 2, 0.07), trim)
    # end wall with an open doorway into a lit room
    dw = 0.9
    rig.box("end_l", (Wd / 2 - dw / 2 + 0.1, 0.12, Hh), (-(Wd / 2 + dw / 2) / 2 - 0.02, L, Hh / 2), paper)
    rig.box("end_r", (Wd / 2 - dw / 2 + 0.1, 0.12, Hh), ((Wd / 2 + dw / 2) / 2 + 0.02, L, Hh / 2), paper)
    rig.box("end_top", (dw, 0.12, Hh - 2.1), (0, L, 2.1 + (Hh - 2.1) / 2), paper)
    rig.box("room_back", (4, 0.1, Hh), (0, L + 3.0, Hh / 2), paper)
    for sx in (-1, 1):
        rig.box(f"room_side{sx}", (0.1, 3.0, Hh), (sx * 2.0, L + 1.5, Hh / 2), paper)
    # a framed picture and a side table with a dead lamp
    rig.box("frame", (0.03, 0.5, 0.4), (-Wd / 2 + 0.01, 2.6, 1.6), rig.principled("pframe", (0.15, 0.1, 0.05)))
    rig.box("pic", (0.035, 0.42, 0.32), (-Wd / 2 + 0.012, 2.6, 1.6), rig.principled("pic", (0.35, 0.33, 0.3)))
    rig.box("table", (0.3, 0.6, 0.8), (Wd / 2 - 0.16, 1.9, 0.4), wood)
    # warm light in the room beyond the doorway; the hallway itself is unlit
    rig.area_light("room", (0, L + 1.6, Hh - 0.1), (0, 0, 0), 1.2, 180, color=(1.0, 0.72, 0.42))
    rig.point_light("lamp", (0.9, L + 2.2, 1.0), 60, color=(1.0, 0.6, 0.3), radius=0.1)
    rig.area_light("moon", (-Wd / 2 + 0.05, 1.0, 1.8), (0, math.radians(-90), 0), 0.6, 6, color=(0.5, 0.6, 1.0))
    heads = []
    pos = (0.05, L + 0.25, 0)
    if it:
        c = creature_at(pos, 0, dict(cast.STAND, look=v(0, -1, 0.05)), smile=1.0)
        heads = [("figure", c)]
        rig.point_light("flash", (-0.1, 0.35, 1.6), 260, color=(0.85, 0.95, 1.0), radius=0.02)
    else:
        # an ordinary, normally proportioned figure: only a silhouette against the doorway
        her = rig.Character("Xbot.glb", "her")
        her.material(rig.principled("shadow", (0.006, 0.005, 0.005), rough=0.8))
        her.root.location = pos
        her.root.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()
        her.pose(dict(cast.STAND, look=v(0.15, -1, -0.05)))
        heads = [("figure", her)]
    rig.world((0.0, 0.0, 0.0), 0.0)
    cam = rig.camera("cam", (-0.15, 0.3, 1.5), (0.05, L, 1.35), lens=24)
    finish(cam, (1200, 900), 96, exposure=0.2, heads=heads)


rig.reset_scene()
bpy.context.scene.render.fps = 30
{"forest": forest,
 "corridor": lambda: corridor(),
 "corridor_end": lambda: corridor(dead_end_lights=True, figure=True),
 "hallway_her": lambda: hallway(False),
 "hallway_it": lambda: hallway(True)}[name]()
