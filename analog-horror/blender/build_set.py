"""Build the restaurant set (static geometry, props, practical lights, exterior) -> set.blend

Coordinates (meters, Z up). Room x:[0,7.6] y:[0,9.6] z:[0,3.2]. CAM 04 sits in the corner near
(0.3, 0.3, 2.85). The window wall is x = 7.6; the bar and kitchen are on the back wall y = 9.6.
"""
import math, os, sys, random
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import setlib as S
from layout import *  # noqa: F401,F403  (shared positions with the character/shot scripts)

out = sys.argv[sys.argv.index("--") + 1]
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.name = "VAMA"
sc.render.fps = 30
sc.unit_settings.system = "METRIC"

C_ROOM = S.coll("room")
C_PROPS = S.coll("props")
C_TABLE = S.coll("couple_table")
C_LIGHTS = S.coll("lights")
C_EXT = S.coll("exterior")
C_KITCHEN = S.coll("kitchen")

# ------------------------------------------------------------------ materials
M_FLOOR = S.pbr("floor_tiles", "floor_tiles_06", tile=1.6, rough_mul=0.75, bump=0.6, coords="Object")
M_WAIN = S.pbr("wainscot", "wooden_panels", tile=1.1, rough_mul=0.9, val=0.7)
M_WALL = S.pbr("wall_plaster", "yellow_plaster", tile=2.5, val=0.85, sat=0.75, tint=(1.0, 0.93, 0.80))
M_BRICK = S.pbr("brick", "red_brick", tile=2.0, val=0.75)
M_CEIL = S.pbr("ceiling", "painted_plaster_wall", tile=2.5, val=0.65, tint=(0.95, 0.9, 0.82))
M_LINEN = S.pbr("linen", "rough_linen", tile=0.35, sat=0.0, val=1.7, tint=(0.96, 0.93, 0.86), bump=0.4)
M_VELVET = S.pbr("velvet", "velour_velvet", tile=0.45, val=0.65)
M_CHERRY = S.pbr("cherry", "lacquered_cherry_wood", tile=1.2)
M_DARKWOOD = S.pbr("darkwood", "dark_wood", tile=1.5, val=0.6)
M_KTILES = S.pbr("kitchen_tiles", "long_white_tiles", tile=1.2)
M_ASPHALT = S.pbr("asphalt", "asphalt_floor", tile=3.0, rough_mul=0.25, val=0.5)
M_SIDEWALK = S.pbr("sidewalk", "brick_pavement", tile=2.0, rough_mul=0.4, val=0.6)
M_GLASS = S.simple("window_glass", (0.85, 0.9, 0.9), rough=0.02, transmission=1.0, ior=1.5)
M_GLASSWARE = S.simple("glassware", (0.95, 0.97, 0.97), rough=0.0, transmission=1.0, ior=1.5)
M_WINE = S.simple("wine", (0.25, 0.01, 0.03), rough=0.05, transmission=0.6, ior=1.34)
M_CERAMIC = S.simple("ceramic", (0.9, 0.88, 0.84), rough=0.15, coat=0.6)
M_STEEL = S.simple("steel", (0.75, 0.75, 0.75), rough=0.25, metal=1.0)
M_BRASS = S.simple("brass", (0.8, 0.6, 0.3), rough=0.3, metal=1.0)
M_BLACKMETAL = S.simple("blackmetal", (0.03, 0.03, 0.03), rough=0.4, metal=0.8)
M_WAX = S.simple("wax", (0.95, 0.9, 0.8), rough=0.4, sss=0.6)
M_FLAME = S.emissive("flame", (1.0, 0.55, 0.15), 25.0)
M_BULB = S.emissive("warm_bulb", S.kelvin(2600), 18.0)
M_FLUO = S.emissive("fluorescent", S.kelvin(5200), 12.0)
M_EXIT = S.emissive("exit_sign", (0.05, 1.0, 0.25), 6.0)
M_PORTHOLE = S.emissive("porthole_glow", S.kelvin(5000), 2.5)
M_BACKLIGHT = S.emissive("bar_backlight", S.kelvin(3000), 4.0)
M_FACADE_WIN = S.emissive("facade_window", S.kelvin(3200), 1.2)
M_FACADE = S.pbr("facade", "red_brick", tile=3.0, val=0.25)
M_STEAK = S.simple("steak", (0.18, 0.06, 0.03), rough=0.45)
M_GREENS = S.simple("greens", (0.08, 0.2, 0.04), rough=0.6)
M_MASH = S.simple("mash", (0.85, 0.75, 0.5), rough=0.7, sss=0.2)
M_SAUCE = S.simple("sauce", (0.25, 0.04, 0.02), rough=0.1)
M_NAPKIN = S.simple("napkin", (0.45, 0.04, 0.05), rough=0.85)

# ------------------------------------------------------------------ room shell
RX, RY, RZ = ROOM
S.box("floor", (-0.2, -0.2, -0.1), (RX + 0.2, RY + 0.2, 0.0), M_FLOOR, C_ROOM)
S.box("ceiling", (-0.2, -0.2, RZ), (RX + 0.2, RY + 0.2, RZ + 0.1), M_CEIL, C_ROOM)
T = 0.15  # wall thickness
WAIN_H = 1.0


def wall_x(name, x, y0, y1, z0, z1, inner_sign):
    """Wall slab perpendicular to X at x (inner face at x)."""
    if inner_sign > 0:
        return S.box(name, (x - T, y0, z0), (x, y1, z1), None, C_ROOM)
    return S.box(name, (x, y0, z0), (x + T, y1, z1), None, C_ROOM)


def finish(ob, z_split=WAIN_H):
    """Assign wainscot below z_split, plaster above (per-face by center height)."""
    me = ob.data
    me.materials.append(M_WAIN)
    me.materials.append(M_WALL)
    for p in me.polygons:
        p.material_index = 0 if (ob.matrix_world @ p.center).z < z_split else 1


def split_box(name, mn, mx):
    """Box split horizontally at the wainscot height so both finishes read correctly."""
    parts = []
    if mn[2] < WAIN_H:
        b = S.box(name + "_lo", mn, (mx[0], mx[1], min(mx[2], WAIN_H)), M_WAIN, C_ROOM)
        parts.append(b)
    if mx[2] > WAIN_H:
        b = S.box(name + "_hi", (mn[0], mn[1], max(mn[2], WAIN_H)), mx, M_WALL, C_ROOM)
        parts.append(b)
    return parts


# left wall (x=0) and front wall (y=0) -- mostly unseen but they bounce light
split_box("wall_left", (-T, 0, 0), (0, RY, RZ))
split_box("wall_front", (0, -T, 0), (RX, 0, RZ))
# back wall (y=RY): brick behind the bar (x<4.3), plaster elsewhere, kitchen door + pass openings
S.box("wall_back_brick", (0, RY, 0), (BAR_X1 + 0.5, RY + T, RZ), M_BRICK, C_ROOM)
door_x0, door_x1 = KITCHEN_DOOR
pass_x0, pass_x1 = KITCHEN_PASS
split_box("wall_back_a", (BAR_X1 + 0.5, RY, 0), (door_x0, RY + T, RZ))
split_box("wall_back_b", (door_x0, RY, 2.15), (door_x1, RY + T, RZ))
split_box("wall_back_c", (door_x1, RY, 0), (pass_x0, RY + T, RZ))
split_box("wall_back_d", (pass_x0, RY, 0), (pass_x1, RY + T, 1.05))
split_box("wall_back_e", (pass_x0, RY, 1.85), (pass_x1, RY + T, RZ))
split_box("wall_back_f", (pass_x1, RY, 0), (RX, RY + T, RZ))
S.box("pass_sill", (pass_x0 - 0.05, RY - 0.18, 1.02), (pass_x1 + 0.05, RY + T + 0.25, 1.07), M_STEEL, C_ROOM)

# window wall (x=RX) with three large windows
segs = []
y = 0.0
for (w0, w1) in WINDOWS:
    split_box(f"wall_win_pier_{w0}", (RX, y, 0), (RX + T, w0, RZ))
    split_box(f"wall_win_sill_{w0}", (RX, w0, 0), (RX + T, w1, WIN_Z[0]))
    split_box(f"wall_win_head_{w0}", (RX, w0, WIN_Z[1]), (RX + T, w1, RZ))
    # frame + mullions + glass
    S.box(f"winframe_b_{w0}", (RX - 0.04, w0, WIN_Z[0] - 0.04), (RX + 0.06, w1, WIN_Z[0] + 0.03), M_DARKWOOD, C_ROOM)
    S.box(f"winframe_t_{w0}", (RX - 0.03, w0, WIN_Z[1] - 0.05), (RX + 0.06, w1, WIN_Z[1]), M_DARKWOOD, C_ROOM)
    S.box(f"winframe_l_{w0}", (RX - 0.03, w0, WIN_Z[0]), (RX + 0.06, w0 + 0.06, WIN_Z[1]), M_DARKWOOD, C_ROOM)
    S.box(f"winframe_r_{w0}", (RX - 0.03, w1 - 0.06, WIN_Z[0]), (RX + 0.06, w1, WIN_Z[1]), M_DARKWOOD, C_ROOM)
    nm = max(1, int((w1 - w0) / 0.9))
    for k in range(1, nm + 1):
        yy = w0 + (w1 - w0) * k / (nm + 1)
        S.box(f"mullion_{w0}_{k}", (RX - 0.02, yy - 0.025, WIN_Z[0]), (RX + 0.04, yy + 0.025, WIN_Z[1]), M_DARKWOOD, C_ROOM)
    S.box(f"transom_{w0}", (RX - 0.02, w0, 2.05), (RX + 0.04, w1, 2.09), M_DARKWOOD, C_ROOM)
    g = S.box(f"glass_{w0}", (RX + 0.005, w0, WIN_Z[0]), (RX + 0.015, w1, WIN_Z[1]), M_GLASS, C_ROOM)
    g.visible_shadow = False
    y = w1
split_box("wall_win_pier_end", (RX, y, 0), (RX + T, RY, RZ))

# trims: baseboard, chair rail, crown
for nm, mn, mx in [("rail_left", (0, 0, WAIN_H - 0.02), (0.035, RY, WAIN_H + 0.04)),
                   ("rail_win", (RX - 0.035, 0, WAIN_H - 0.02), (RX, RY, WAIN_H + 0.04)),
                   ("crown_left", (0, 0, RZ - 0.1), (0.06, RY, RZ)), ("crown_win", (RX - 0.06, 0, RZ - 0.1), (RX, RY, RZ)),
                   ("crown_back", (0, RY - 0.06, RZ - 0.1), (RX, RY, RZ)),
                   ("base_left", (0, 0, 0), (0.02, RY, 0.12)), ("base_win", (RX - 0.02, 0, 0), (RX, RY, 0.12))]:
    S.box(nm, mn, mx, M_DARKWOOD, C_ROOM)
# ceiling beams
for k in range(1, 5):
    yy = RY * k / 5
    S.box(f"beam_{k}", (0, yy - 0.09, RZ - 0.22), (RX, yy + 0.09, RZ), M_DARKWOOD, C_ROOM)

# ------------------------------------------------------------------ bar
bx0, bx1 = BAR_X0, BAR_X1
S.box("bar_front", (bx0, BAR_Y - 0.55, 0), (bx1, BAR_Y, 1.02), M_DARKWOOD, C_PROPS, bevel=0.01)
S.box("bar_top", (bx0 - 0.05, BAR_Y - 0.62, 1.02), (bx1 + 0.05, BAR_Y + 0.02, 1.07), M_CHERRY, C_PROPS, bevel=0.01)
S.box("bar_footrail", (bx0, BAR_Y - 0.66, 0.18), (bx1, BAR_Y - 0.62, 0.22), M_BRASS, C_PROPS)
S.box("backbar", (bx0, RY - 0.45, 0), (bx1, RY, 0.95), M_DARKWOOD, C_PROPS)
S.box("backbar_top", (bx0, RY - 0.47, 0.95), (bx1, RY, 0.99), M_CHERRY, C_PROPS)
for k, zz in enumerate((1.35, 1.75, 2.15)):
    S.box(f"backshelf_{k}", (bx0 + 0.2, RY - 0.25, zz), (bx1 - 0.2, RY, zz + 0.03), M_DARKWOOD, C_PROPS)
    S.box(f"backlight_{k}", (bx0 + 0.25, RY - 0.03, zz + 0.03), (bx1 - 0.25, RY - 0.01, zz + 0.06), M_BACKLIGHT, C_PROPS)
bot_root, bots = S.import_gltf("wine_bottles_01", C_PROPS, "bottles_src")
bottle_meshes = [o for o in bots if o.type == "MESH"]
for o in bottle_meshes:
    o.hide_render = o.hide_viewport = True
for k, zz in enumerate((1.38, 1.78, 2.18)):
    xx = bx0 + 0.35
    while xx < bx1 - 0.35:
        src = random.choice(bottle_meshes)
        dup = src.copy()
        dup.data = src.data
        dup.parent = None
        dup.hide_render = dup.hide_viewport = False
        C_PROPS.objects.link(dup)
        dup.matrix_world = src.matrix_world.copy()
        dup.location = (xx, RY - 0.13, zz)
        dup.rotation_euler = (0, 0, random.uniform(0, 6.28))
        xx += random.uniform(0.11, 0.16)
for k, xx in enumerate(BAR_STOOLS):
    S.import_gltf("bar_chair_round_01", C_PROPS, f"barstool_{k}", (xx, BAR_Y - 0.95, 0), random.uniform(0, 6.28))

# wall clock above the bar, hands set to 9:47
clk, clk_parts = S.import_gltf("wall_clock", C_PROPS, "wall_clock", CLOCK_POS, 0.0)
clk.rotation_euler = (0, 0, math.pi)  # face into the room (-Y)
for o in clk_parts:
    if "hours_hand" in o.name:
        o.rotation_euler.rotate_axis("Y", -math.radians((9 + 47 / 60) * 30))
    elif "minute_hand" in o.name:
        o.rotation_euler.rotate_axis("Y", -math.radians(47 * 6))
    elif "second_hand" in o.name:
        o["vama_second_hand"] = 1

# kitchen door (double swing, porthole windows) + EXIT sign
for k, (a, b) in enumerate(((door_x0, (door_x0 + door_x1) / 2), ((door_x0 + door_x1) / 2, door_x1))):
    S.box(f"kdoor_{k}", (a + 0.01, RY + 0.02, 0.02), (b - 0.01, RY + 0.07, 2.12), M_STEEL, C_PROPS)
    S.cylinder(f"porthole_{k}", 0.13, 0.06, ((a + b) / 2, RY + 0.015, 1.5), M_PORTHOLE, C_PROPS).rotation_euler = (math.pi / 2, 0, 0)
S.box("exit_sign", (door_x0 + 0.15, RY - 0.06, 2.3), (door_x1 - 0.15, RY - 0.02, 2.48), M_EXIT, C_PROPS)
txt = bpy.data.curves.new("exit_txt", "FONT")
txt.body = "EXIT"
txt.size = 0.12
txt.align_x = "CENTER"
to = bpy.data.objects.new("exit_text", txt)
C_PROPS.objects.link(to)
to.location = ((door_x0 + door_x1) / 2, RY - 0.065, 2.345)
to.rotation_euler = (math.pi / 2, 0, 0)
to.data.materials.append(S.simple("exit_black", (0.0, 0.05, 0.01), rough=0.5))

# kitchen room behind the back wall (seen through door portholes and the pass)
KY0, KY1 = RY + T, RY + 3.5
S.box("k_floor", (BAR_X1, KY0, -0.05), (RX, KY1, 0), M_KTILES, C_KITCHEN)
S.box("k_back", (BAR_X1, KY1, 0), (RX, KY1 + 0.1, RZ), M_KTILES, C_KITCHEN)
S.box("k_side", (RX, KY0, 0), (RX + 0.1, KY1, RZ), M_KTILES, C_KITCHEN)
S.box("k_side2", (BAR_X1 + 0.4, KY0, 0), (BAR_X1 + 0.5, KY1, RZ), M_KTILES, C_KITCHEN)
S.box("k_ceil", (BAR_X1, KY0, RZ), (RX, KY1, RZ + 0.1), M_CEIL, C_KITCHEN)
S.box("k_counter", (pass_x0 - 0.6, RY + 0.55, 0), (RX - 0.1, RY + 1.15, 0.92), M_STEEL, C_KITCHEN)
sh, _ = S.import_gltf("steel_frame_shelves_01", C_KITCHEN, "k_shelves", (6.2, KY1 - 0.3, 0), math.pi, 0.1)
fl, _ = S.import_gltf("mounted_fluorescent_lights", C_KITCHEN, "k_fluo", (6.0, RY + 1.6, RZ), 0)
S.area_light("k_fluo_light", (6.0, RY + 1.6, RZ - 0.06), (0, 0, 0), 180, 0.9, S.kelvin(5000), C_LIGHTS, size_y=0.6)

# ------------------------------------------------------------------ booths along the left wall
for k, by in enumerate(BOOTHS):
    for side in (-1, 1):
        yy = by + side * 0.62
        S.box(f"booth{k}_seat_{side}", (0.05, yy - 0.25, 0.0), (0.95, yy + 0.25, 0.45), M_VELVET, C_PROPS, bevel=0.03)
        back_y = yy + side * 0.22
        S.box(f"booth{k}_back_{side}", (0.05, back_y - 0.06, 0.45), (0.95, back_y + 0.08, 1.15), M_VELVET, C_PROPS, bevel=0.03)
        S.box(f"booth{k}_cap_{side}", (0.05, back_y - 0.07, 1.15), (0.95, back_y + 0.09, 1.19), M_DARKWOOD, C_PROPS)
    S.box(f"booth{k}_table", (0.05, by - 0.35, 0.72), (0.85, by + 0.35, 0.76), M_CHERRY, C_PROPS, bevel=0.01)
    S.cylinder(f"booth{k}_ped", 0.05, 0.72, (0.45, by, 0), M_BLACKMETAL, C_PROPS)

# pictures / sconces on the left wall
S.import_gltf("fancy_picture_frame_01", C_PROPS, "pic_a", (0.03, BOOTHS[0], 1.75), -math.pi / 2)
S.import_gltf("hanging_picture_frame_02", C_PROPS, "pic_b", (0.04, BOOTHS[1], 1.75), -math.pi / 2)
S.import_gltf("hanging_picture_frame_01", C_PROPS, "pic_c", (0.03, 2.2, 1.65), -math.pi / 2)
for k, yy in enumerate(SCONCES):
    S.import_gltf("industrial_wall_lamp", C_PROPS, f"sconce_{k}", (0.0, yy, 2.0), -math.pi / 2)
    S.point_light(f"sconce_light_{k}", (0.12, yy, 1.95), 25, S.kelvin(2400), 0.06, C_LIGHTS)
S.import_gltf("potted_plant_01", C_PROPS, "plant_a", (RX - 0.45, 0.6, 0), 0.3)
S.import_gltf("potted_plant_02", C_PROPS, "plant_b", (BAR_X1 + 0.75, RY - 0.45, 0), 1.2)
S.import_gltf("wine_barrel_01", C_PROPS, "barrel", (0.45, RY - 0.5, 0), 0.4)

# ------------------------------------------------------------------ tables + tablecloths
def cloth_drape(name, kind, top_z, half):
    """Simulate a tablecloth falling on a table-top proxy; returns the applied mesh object."""
    if kind == "rect":
        prx = S.box(name + "_proxy", (-half[0], -half[1], top_z - 0.04), (half[0], half[1], top_z), None)
        cw, ch = half[0] * 2 + 0.17, half[1] * 2 + 0.17
    else:
        prx = S.cylinder(name + "_proxy", half[0], 0.04, (0, 0, top_z - 0.04), None)
        cw = ch = half[0] * 2 + 0.17      # ~8.5 cm drop: the hem stays above seated diners' thighs
    prx.modifiers.new("col", "COLLISION").settings.thickness_outer = 0.004
    cl = S.plane(name, cw, ch, (0, 0, top_z + 0.02), subdiv=70)
    m = cl.modifiers.new("cloth", "CLOTH")
    m.settings.quality = 8
    m.settings.mass = 0.2
    m.settings.tension_stiffness = 25
    m.settings.bending_stiffness = 0.6
    m.collision_settings.distance_min = 0.004
    m.collision_settings.use_self_collision = False
    m.point_cache.frame_end = 60
    for f in range(1, 46):
        sc.frame_set(f)
    bpy.context.view_layer.objects.active = cl
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cl.evaluated_get(dg))
    bpy.data.objects.remove(cl, do_unlink=True)
    bpy.data.objects.remove(prx, do_unlink=True)
    sc.frame_set(1)
    ob = bpy.data.objects.new(name, me)
    ob["z0"] = top_z + 0.02  # mesh is local to the simulated plane's origin
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(M_LINEN)
    sol = ob.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.003
    ob.modifiers.new("smooth", "SUBSURF").levels = 1
    return ob


CLOTH_RECT = cloth_drape("cloth_rect", "rect", COUPLE_TABLE_TOP, (0.567, 0.353))
CLOTH_ROUND = cloth_drape("cloth_round", "round", 0.746, (0.398,))


def place_setting(prefix, pos, yaw, c, food=True, glass_full=0.5):
    """Plate (+food), wine glass, cutlery, napkin for one diner. pos is the plate center."""
    px, py, pz = pos
    plate = S.lathe(prefix + "_plate", [(0.0, 0.0), (0.075, 0.0), (0.085, 0.006), (0.105, 0.012), (0.135, 0.022),
                                        (0.138, 0.024), (0.0, 0.009)], M_CERAMIC, c, 48, (px, py, pz))
    plate.data.materials.clear(); plate.data.materials.append(M_CERAMIC)
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))  # diner looks along fwd; table center is ahead
    side = Vector((math.cos(yaw), math.sin(yaw), 0))
    if food:
        st = S.box(prefix + "_steak", (-0.055, -0.035, 0), (0.055, 0.035, 0.022), M_STEAK, c, bevel=0.012)
        st.location = Vector((px, py, pz + 0.011)) + side * 0.015 - fwd * 0.01
        st.rotation_euler = (0, 0, yaw + 0.4)
        mash = S.lathe(prefix + "_mash", [(0.0, 0.0), (0.035, 0.0), (0.03, 0.02), (0.0, 0.03)], M_MASH, c, 24,
                       tuple(Vector((px, py, pz + 0.011)) - side * 0.055 + fwd * 0.03))
        for i in range(4):
            sp = S.box(prefix + f"_asp{i}", (-0.006, -0.05, 0), (0.006, 0.05, 0.008), M_GREENS, c, bevel=0.003)
            sp.location = Vector((px, py, pz + 0.012)) + side * (0.03 + 0.012 * i) + fwd * 0.045
            sp.rotation_euler = (0, 0, yaw + 1.2)
        sauce = S.cylinder(prefix + "_sauce", 0.03, 0.002, tuple(Vector((px, py, pz + 0.011)) + side * 0.06 - fwd * 0.04), M_SAUCE, c)
    gpos = Vector((px, py, pz)) + side * 0.15 + fwd * 0.12
    S.lathe(prefix + "_glass", [(0.0, 0.0), (0.036, 0.0), (0.036, 0.003), (0.004, 0.006), (0.004, 0.09),
                                (0.03, 0.11), (0.042, 0.15), (0.038, 0.2), (0.036, 0.2), (0.04, 0.15), (0.028, 0.112),
                                (0.0, 0.1)], M_GLASSWARE, c, 32, tuple(gpos))
    if glass_full > 0:
        h = 0.11 + 0.05 * glass_full
        S.lathe(prefix + "_wine", [(0.0, 0.105), (0.026, 0.112), (0.038, 0.15 if h > 0.15 else h), (0.0, h)],
                M_WINE, c, 32, tuple(gpos))
    for k, off in enumerate((-0.18, 0.18)):
        cpos = Vector((px, py, pz + 0.002)) + side * off
        cut = S.box(prefix + f"_cutlery{k}", (-0.008, -0.1, 0), (0.008, 0.1, 0.004), M_STEEL, c, bevel=0.002)
        cut.location = cpos
        cut.rotation_euler = (0, 0, yaw)
    nap = S.box(prefix + "_napkin", (-0.06, -0.09, 0), (0.06, 0.09, 0.012), M_NAPKIN, c, bevel=0.005)
    nap.location = Vector((px, py, pz + 0.001)) - side * 0.27
    nap.rotation_euler = (0, 0, yaw)


def candle(prefix, pos, c, light_power=1.2):
    x, y, z = pos
    S.lathe(prefix + "_votive", [(0.0, 0.0), (0.035, 0.0), (0.037, 0.075), (0.033, 0.075), (0.031, 0.004), (0.0, 0.004)],
            M_GLASSWARE, c, 24, (x, y, z))
    S.cylinder(prefix + "_wax", 0.028, 0.035, (x, y, z + 0.004), M_WAX, c)
    fl = S.lathe(prefix + "_flame", [(0.0, 0.0), (0.004, 0.006), (0.003, 0.014), (0.0, 0.022)], M_FLAME, c, 12,
                 (x, y, z + 0.04))
    fl.visible_shadow = False
    L = S.point_light(prefix + "_light", (x, y, z + 0.055), light_power, S.kelvin(1900), 0.01, C_LIGHTS)
    L["vama_candle"] = 1
    return L


def table(prefix, kind, center, rot_z, c, diners):
    """kind 'rect' (wooden_table_02 scaled to 0.75 m) or 'round' (round_wooden_table_02)."""
    if kind == "rect":
        root, parts = S.import_gltf("wooden_table_02", c, prefix + "_table", center, rot_z)
        root.scale = (1.0, 1.0, COUPLE_TABLE_TOP / 0.799)
        top = COUPLE_TABLE_TOP
        cl = CLOTH_RECT.copy()
    else:
        root, parts = S.import_gltf("round_wooden_table_02", c, prefix + "_table", center, rot_z)
        top = 0.746
        cl = CLOTH_ROUND.copy()
    cl.name = prefix + "_cloth"
    c.objects.link(cl)
    cl.location = (center[0], center[1], cl["z0"])
    cl.rotation_euler = (0, 0, rot_z)
    for k, (dyaw, dist) in enumerate(diners):
        yaw = rot_z + dyaw
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))
        ppos = Vector(center) - fwd * dist
        place_setting(f"{prefix}_d{k}", (ppos.x, ppos.y, top + 0.012), yaw, c)
    return top


# couple table (hero) -- the man sits on the -Y side facing +Y, the woman on +Y facing -Y
table("couple", "round", COUPLE_TABLE, 0.0, C_TABLE, [(WOMAN_YAW, 0.19), (MAN_YAW, 0.19)])
candle("couple", (COUPLE_TABLE[0], COUPLE_TABLE[1] - 0.25, COUPLE_TABLE_TOP + 0.012), C_TABLE, 1.4)
bot = [o for o in bottle_meshes if "bordeaux" in o.name][0].copy()
bot.data = bot.data
bot.parent = None
bot.hide_render = bot.hide_viewport = False
C_TABLE.objects.link(bot)
# south-west corner of the table: clear of his reach path (he stands on the north side) and of the slam
bot.location = (COUPLE_TABLE[0] - 0.18, COUPLE_TABLE[1] - 0.17, COUPLE_TABLE_TOP + 0.012)
bot.scale = (1, 1, 1)
bot.name = "couple_bottle"
for k, (cpos, yaw) in enumerate(COUPLE_CHAIRS):
    S.import_gltf("dining_chair_02", C_TABLE, ["chair_man", "chair_woman"][k], cpos, yaw)

for t in OTHER_TABLES:
    top = table(t["name"], t["kind"], t["center"], t.get("rot", 0.0), C_PROPS,
                [(d["yaw"] - t.get("rot", 0.0), 0.22) for d in t["diners"]])
    candle(t["name"], (t["center"][0], t["center"][1] + 0.05, top + 0.012), C_PROPS, 1.0)
    for d in t["diners"]:
        if d.get("chair", True):
            S.import_gltf("dining_chair_02", C_PROPS, f"{t['name']}_chair_{d['tag']}", d["chair_pos"], d["yaw"])

for d in BOOTH_DINERS:
    fwd = Vector((math.sin(d["yaw"]), -math.cos(d["yaw"]), 0))
    pp = Vector((d["pelvis"][0], d["pelvis"][1], 0)) + fwd * 0.42
    place_setting(f"booth_{d['tag']}", (pp.x, pp.y, 0.76 + 0.012), d["yaw"], C_PROPS)
for k, by in enumerate(BOOTHS):
    candle(f"booth{k}", (0.3, by, 0.772), C_PROPS, 0.8)

# ------------------------------------------------------------------ ceiling lights
PSCALE = 0.62
for k, (lx, ly) in enumerate(PENDANTS):
    root, parts = S.import_gltf("modern_ceiling_lamp_01", C_PROPS, f"pendant_{k}", (lx, ly, 0), 0, PSCALE)
    root.location.z = RZ - 1.173 * PSCALE
    # globe center sits ~0.36 above the lamp's lowest point (scaled)
    L = S.point_light(f"pendant_light_{k}", (lx, ly, RZ - 1.173 * PSCALE + (0.221 + 0.22) * PSCALE), 45,
                      S.kelvin(2500), 0.06, C_LIGHTS)
    L["vama_pendant"] = k
ch_root, _ = S.import_gltf("Chandelier_01", C_PROPS, "chandelier", (CHANDELIER[0], CHANDELIER[1], RZ), 0)
for k in range(6):
    a = k * math.pi / 3
    S.point_light(f"chand_light_{k}", (CHANDELIER[0] + 0.28 * math.cos(a), CHANDELIER[1] + 0.28 * math.sin(a), RZ - 0.55),
                  14, S.kelvin(2400), 0.03, C_LIGHTS)
# soft fill so the shadows aren't pitch black (bounce from warm walls)
S.area_light("fill_room", (RX / 2, RY / 2, RZ - 0.05), (0, 0, 0), 120, 5.0, S.kelvin(2700), C_LIGHTS, size_y=7.0)

# ------------------------------------------------------------------ exterior (night street, wet)
S.box("street", (RX + 3.0, -10, -0.15), (RX + 12, RY + 10, -0.1), M_ASPHALT, C_EXT)
S.box("sidewalk", (RX + 0.15, -10, -0.1), (RX + 3.0, RY + 10, 0.0), M_SIDEWALK, C_EXT)
S.box("curb", (RX + 2.9, -10, -0.15), (RX + 3.05, RY + 10, 0.0), S.simple("curb", (0.35, 0.35, 0.33), 0.6), C_EXT)
S.box("facade", (RX + 12, -10, -0.15), (RX + 12.5, RY + 10, 12), M_FACADE, C_EXT)
for k in range(9):
    for j in range(3):
        if random.random() < 0.4:
            yy = -6 + k * 2.6
            S.box(f"fwin_{k}_{j}", (RX + 11.98, yy, 1.2 + j * 3.2), (RX + 12.0, yy + 1.1, 2.6 + j * 3.2), M_FACADE_WIN, C_EXT)
for k, yy in enumerate((1.0, 9.5)):
    S.import_gltf("street_lamp_01", C_EXT, f"streetlamp_{k}", (RX + 2.6, yy, 0.0), math.pi / 2)
    L = S.point_light(f"streetlamp_light_{k}", (RX + 2.3, yy, 3.55), 2500, S.kelvin(2000), 0.15, C_LIGHTS)
    L["vama_streetlamp"] = k
w = bpy.data.worlds.new("night")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.006, 0.012, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w

# car headlights (animated by the shot script): a pair of spots parked off-screen
for k in range(2):
    s = S.spot_light(f"car_light_{k}", (RX + 6.5, -30, 0.7), (math.pi / 2, 0, 0), 0, math.radians(35),
                     S.kelvin(4300), C_LIGHTS, 0.4, 0.1)
    s["vama_carlight"] = k

# ------------------------------------------------------------------ render defaults
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 64
if hasattr(sc.eevee, "shadow_pool_size"):
    sc.eevee.shadow_pool_size = "2048"
for o in C_LIGHTS.objects:
    if o.type != "LIGHT":
        continue
    hero = o.name.startswith(("couple_", "pendant_light_0", "streetlamp", "car_light", "k_fluo"))
    if not hero and (o.get("vama_candle") or o.name.startswith(("chand_light", "fill_room", "sconce"))):
        o.data.use_shadow = False
    if hasattr(o.data, "shadow_resolution_limit"):
        o.data.shadow_resolution_limit = 0.01 if not hero else 0.002
for attr, val in (("use_raytracing", True), ("use_shadows", True), ("use_volumetric_shadows", False)):
    if hasattr(sc.eevee, attr):
        setattr(sc.eevee, attr, val)
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast"
sc.render.resolution_x, sc.render.resolution_y = 1280, 960
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("SAVED", out)
