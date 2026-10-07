"""Geometry/material helpers for building the restaurant set procedurally."""
import math, os
import bpy, bmesh
from mathutils import Vector, Matrix

PH = os.environ.get("VAMA_POLYHAVEN", r"D:\VAMA_work\assets\polyhaven")


# ---------------------------------------------------------------- collections
def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in [x.name for x in p.children]:
        p.children.link(c)
    return c


def link(obj, c):
    for uc in list(obj.users_collection):
        uc.objects.unlink(obj)
    c.objects.link(obj)
    return obj


# ---------------------------------------------------------------- materials
def _tex(nt, path, colorspace, x, y, proj="BOX"):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = colorspace
    n.projection = proj
    n.projection_blend = 0.25
    n.location = (x, y)
    return n


def pbr(name, tex_id, tile=1.0, tint=None, rough_mul=1.0, bump=1.0, proj="BOX", coords="Object", sat=1.0, val=1.0):
    """Poly Haven texture set material using object-space box projection (meters)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (200, 0)
    nt.links.new(b.outputs[0], out.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1100, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-900, 0)
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1 / tile)
    nt.links.new(tc.outputs[coords], mp.inputs["Vector"])
    d = os.path.join(PH, "tex", tex_id)
    files = {f.split(".")[0]: os.path.join(d, f) for f in os.listdir(d)}
    if "Diffuse" in files:
        t = _tex(nt, files["Diffuse"], "sRGB", -600, 300, proj)
        nt.links.new(mp.outputs[0], t.inputs[0])
        col = t.outputs["Color"]
        if tint or sat != 1.0 or val != 1.0:
            hsv = nt.nodes.new("ShaderNodeHueSaturation")
            hsv.location = (-300, 300)
            hsv.inputs["Saturation"].default_value = sat
            hsv.inputs["Value"].default_value = val
            nt.links.new(col, hsv.inputs["Color"])
            col = hsv.outputs["Color"]
            if tint:
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.blend_type = "MULTIPLY"
                mix.location = (-100, 300)
                mix.inputs["Factor"].default_value = 1.0
                mix.inputs[7].default_value = (*tint, 1)
                nt.links.new(col, mix.inputs[6])
                col = mix.outputs[2]
        nt.links.new(col, b.inputs["Base Color"])
    if "Rough" in files:
        t = _tex(nt, files["Rough"], "Non-Color", -600, 0, proj)
        nt.links.new(mp.outputs[0], t.inputs[0])
        mth = nt.nodes.new("ShaderNodeMath")
        mth.operation = "MULTIPLY"
        mth.inputs[1].default_value = rough_mul
        mth.location = (-300, 0)
        nt.links.new(t.outputs["Color"], mth.inputs[0])
        nt.links.new(mth.outputs[0], b.inputs["Roughness"])
    if "nor_gl" in files and bump > 0:
        t = _tex(nt, files["nor_gl"], "Non-Color", -600, -300, proj)
        nt.links.new(mp.outputs[0], t.inputs[0])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-300, -300)
        nm.inputs["Strength"].default_value = bump
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m


def simple(name, color, rough=0.5, metal=0.0, emission=None, strength=0.0, alpha=1.0, transmission=0.0, ior=1.45,
           sss=0.0, coat=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    if transmission > 0:
        m.surface_render_method = "DITHERED"
        try:
            m.use_raytrace_refraction = True
        except AttributeError:
            pass
    return m


def emissive(name, color, strength):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*color, 1)
    e.inputs[1].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


# ---------------------------------------------------------------- geometry
def box(name, mn, mx, mat=None, c=None, bevel=0.0):
    """Axis-aligned box from world-space min/max corners (mesh in world coords)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    mn, mx = Vector(mn), Vector(mx)
    size = mx - mn
    ctr = (mx + mn) / 2
    for v in bm.verts:
        v.co = Vector((v.co.x * size.x, v.co.y * size.y, v.co.z * size.z)) + ctr
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (c or bpy.context.scene.collection).objects.link(ob)
    if mat:
        me.materials.append(mat)
    if bevel > 0:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
        md.limit_method = "ANGLE"
    return ob


def lathe(name, profile, mat=None, c=None, steps=48, loc=(0, 0, 0), smooth=True):
    """Revolve a (r, z) profile around Z."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in profile])
    for i in range(steps):
        r0, r1 = rings[i], rings[(i + 1) % steps]
        for j in range(len(profile) - 1):
            bm.faces.new((r0[j], r1[j], r1[j + 1], r0[j + 1]))
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    (c or bpy.context.scene.collection).objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def cylinder(name, r, h, loc, mat=None, c=None, verts=32):
    return lathe(name, [(0.0, 0.0), (r, 0.0), (r, h), (0.0, h)], mat, c, verts, loc, smooth=False)


def plane(name, w, h, loc, rot=(0, 0, 0), mat=None, c=None, subdiv=0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=subdiv + 1, y_segments=subdiv + 1, size=0.5)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= h
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    (c or bpy.context.scene.collection).objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def import_gltf(asset_id, c, name=None, loc=(0, 0, 0), rot_z=0.0, scale=1.0):
    """Import a Poly Haven glTF; parent all parts to an empty so it moves as one unit."""
    d = os.path.join(PH, "models", asset_id)
    f = next(os.path.join(d, x) for x in os.listdir(d) if x.endswith(".gltf"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name or asset_id, None)
    c.objects.link(root)
    for o in new:
        link(o, c)
        if o.parent is None:
            o.parent = root
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    root.scale = (scale, scale, scale)
    return root, new


def bounds(objs):
    """World-space AABB of mesh objects."""
    bpy.context.view_layer.update()
    mn = Vector((1e9, 1e9, 1e9))
    mx = -mn
    for o in objs:
        if o.type != "MESH":
            continue
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


def point_light(name, loc, power, color=(1.0, 0.75, 0.5), radius=0.05, c=None, shadow=True):
    l = bpy.data.lights.new(name, "POINT")
    l.energy = power
    l.color = color
    l.shadow_soft_size = radius
    l.use_shadow = shadow
    o = bpy.data.objects.new(name, l)
    o.location = loc
    (c or bpy.context.scene.collection).objects.link(o)
    return o


def area_light(name, loc, rot, power, size, color=(1, 1, 1), c=None, shape="RECTANGLE", size_y=None):
    l = bpy.data.lights.new(name, "AREA")
    l.energy = power
    l.color = color
    l.shape = shape
    l.size = size
    if size_y:
        l.size_y = size_y
    o = bpy.data.objects.new(name, l)
    o.location = loc
    o.rotation_euler = rot
    (c or bpy.context.scene.collection).objects.link(o)
    return o


def spot_light(name, loc, rot, power, angle, color=(1, 1, 1), c=None, blend=0.3, radius=0.05):
    l = bpy.data.lights.new(name, "SPOT")
    l.energy = power
    l.color = color
    l.spot_size = angle
    l.spot_blend = blend
    l.shadow_soft_size = radius
    o = bpy.data.objects.new(name, l)
    o.location = loc
    o.rotation_euler = rot
    (c or bpy.context.scene.collection).objects.link(o)
    return o


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def kelvin(k):
    """Approximate blackbody RGB (linear-ish) for light colors."""
    t = k / 100.0
    if t <= 66:
        r = 1.0
        g = max(0, min(1, (99.4708025861 * math.log(t) - 161.1195681661) / 255))
        b = 0 if t <= 19 else max(0, min(1, (138.5177312231 * math.log(t - 10) - 305.0447927307) / 255))
    else:
        r = max(0, min(1, 329.698727446 * ((t - 60) ** -0.1332047592) / 255))
        g = max(0, min(1, 288.1221695283 * ((t - 60) ** -0.0755148492) / 255))
        b = 1.0
    return (r ** 2.2, g ** 2.2, b ** 2.2)
