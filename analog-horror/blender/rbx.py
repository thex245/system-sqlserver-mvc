"""Microsoft Rocketbox avatar helpers for Blender 5.x.

Imports the *_facial.fbx variant (15 visemes + ARKit/FACS blendshapes), rebuilds
materials as physically based shaders and exposes small helpers used by the
scene/animation scripts.
"""
import os
import bpy

ROCKETBOX = os.environ.get("VAMA_ROCKETBOX", r"D:\VAMA_work\assets\rocketbox\Assets")


def avatar_dir(name):
    for cat in ("Adults", "Professions", "Children"):
        d = os.path.join(ROCKETBOX, "Avatars", cat, name)
        if os.path.isdir(d):
            return d
    raise FileNotFoundError(name)


def _img(path, colorspace="sRGB"):
    if not os.path.exists(path):
        alt = os.path.splitext(path)[0] + ".png"  # downscaled extras (tools/downscale_textures.py)
        if not os.path.exists(alt):
            return None
        path = alt
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def _texset(tex_dir, mat_name):
    """Material 'f015_head' -> textures f015_head_{color,normal,specular}.tga."""
    base = mat_name.split(".")[0]
    p = lambda s: os.path.join(tex_dir, f"{base}_{s}.tga")
    return {
        "color": _img(p("color")),
        "normal": _img(p("normal"), "Non-Color"),
        "spec": _img(p("specular"), "Non-Color"),
        "opacity": _img(p("opacity_color")) or _img(os.path.join(tex_dir, f"{base}_color.tga")),
    }


def build_material(mat, tex_dir, kind):
    """kind: 'skin' (head), 'cloth' (body), 'hair' (opacity), 'glasses'."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (-300, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tx = _texset(tex_dir, mat.name)

    def tex(img, x, y):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.location = (x, y)
        n.interpolation = "Cubic"
        return n

    col_img = tx["opacity"] if kind in ("hair", "glasses") else tx["color"]
    if col_img:
        c = tex(col_img, -900, 300)
        if kind == "skin":
            # Slightly desaturate/warm the baked diffuse so it survives subsurface.
            hsv = nt.nodes.new("ShaderNodeHueSaturation")
            hsv.location = (-600, 300)
            hsv.inputs["Saturation"].default_value = 0.92
            hsv.inputs["Value"].default_value = 0.95
            nt.links.new(c.outputs["Color"], hsv.inputs["Color"])
            nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            nt.links.new(c.outputs["Color"], bsdf.inputs["Base Color"])
        if kind in ("hair", "glasses"):
            nt.links.new(c.outputs["Alpha"], bsdf.inputs["Alpha"])
    if tx["normal"]:
        n = tex(tx["normal"], -900, -300)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-600, -300)
        nm.inputs["Strength"].default_value = 0.8 if kind == "skin" else 1.0
        nt.links.new(n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if tx["spec"]:
        s = tex(tx["spec"], -900, 0)
        # specular (glossiness-ish) -> roughness
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.location = (-600, 0)
        lo, hi = {"skin": (0.62, 0.38), "hair": (0.75, 0.45), "cloth": (0.9, 0.55), "glasses": (0.3, 0.1)}[kind]
        mr.inputs["To Min"].default_value = lo
        mr.inputs["To Max"].default_value = hi
        sep = nt.nodes.new("ShaderNodeRGBToBW")
        sep.location = (-750, 0)
        nt.links.new(s.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Val"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.6
    if kind == "skin":
        bsdf.inputs["Subsurface Weight"].default_value = 0.18
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        bsdf.inputs["Subsurface Scale"].default_value = 0.012
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    if kind == "cloth":
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
        bsdf.inputs["Sheen Weight"].default_value = 0.15
    if kind in ("hair", "glasses"):
        mat.surface_render_method = "DITHERED"
        if kind == "glasses":
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def classify(mat_name):
    n = mat_name.lower()
    if "glasses" in n:
        return "glasses"
    if "opacity" in n:
        return "hair"
    if "head" in n:
        return "skin"
    return "cloth"


def import_avatar(name, facial=True, collection=None, tag=None):
    """Import a Rocketbox avatar; returns (armature, mesh)."""
    d = avatar_dir(name)
    fbx = os.path.join(d, "Export", f"{name}_facial.fbx" if facial else f"{name}.fbx")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx, use_anim=False, ignore_leaf_bones=False,
                             automatic_bone_orientation=False)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    meshes = [o for o in new if o.type == "MESH"]
    # Keep only the highest-detail mesh (FBX ships several LODs in some avatars).
    meshes.sort(key=lambda o: len(o.data.polygons), reverse=True)
    mesh = meshes[0]
    for m in meshes[1:]:
        bpy.data.objects.remove(m, do_unlink=True)
    tag = tag or name
    # Normalise the rig object to the origin (the FBX root node stores pelvis height on the
    # object); poses are always baked in world space, see anim.bake_clip.
    import anim
    arm.matrix_world = anim.rest_matrix(arm)
    arm.name = f"{tag}_rig"
    mesh.name = f"{tag}_body"
    tex_dir = os.path.join(d, "Textures")
    for slot in mesh.material_slots:
        if slot.material:
            m = slot.material.copy()
            m.name = slot.material.name  # keep texture-prefix name for lookup
            build_material(m, tex_dir, classify(m.name))
            m.name = f"{tag}_{slot.material.name}"
            slot.material = m
    if collection:
        for o in (arm, mesh):
            for c in o.users_collection:
                c.objects.unlink(o)
            collection.objects.link(o)
    mesh["vama_tag"] = tag
    arm["vama_tag"] = tag
    return arm, mesh


def set_keys(mesh, values, frame=None):
    kb = mesh.data.shape_keys.key_blocks
    for k, v in values.items():
        if k in kb:
            kb[k].value = v
            if frame is not None:
                kb[k].keyframe_insert("value", frame=frame)
