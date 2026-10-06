"""Shared Blender helpers: character import, joint-aiming pose system, materials,
render settings and screen-space tracking export.

Runs inside the `bpy` module (pip install bpy==5.2.2): `python3 film/blender/<scene>.py`.

Poses are written in *character space*: the character faces -Y, +Z is up and
its right hand is on -X. Each limb is described by the direction its segment
should point (joint -> next joint), so poses are independent of how each model's
bones happen to be rolled.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MESHES, RENDERS  # noqa: E402

P = "mixamorig:"

# segment -> joint that ends it
CHILD = {
    "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Neck", "Neck": "Head",
    "LeftShoulder": "LeftArm", "LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand",
    "LeftHand": "LeftHandMiddle1",
    "RightShoulder": "RightArm", "RightArm": "RightForeArm", "RightForeArm": "RightHand",
    "RightHand": "RightHandMiddle1",
    "LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot", "LeftFoot": "LeftToeBase",
    "RightUpLeg": "RightLeg", "RightLeg": "RightFoot", "RightFoot": "RightToeBase",
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def v(*a):
    return Vector(a).normalized()


class Character:
    """An imported Mixamo-rigged glTF character wrapped in a root empty."""

    def __init__(self, glb, name, faces_neg_y=True):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(MESHES / glb), bone_heuristic="TEMPERANCE")
        new = [o for o in bpy.data.objects if o not in before]
        for o in list(new):
            if o.name.startswith("Icosphere"):
                bpy.data.objects.remove(o)
                new.remove(o)
        self.arm = next(o for o in new if o.type == "ARMATURE")
        self.meshes = [o for o in new if o.type == "MESH"]
        self.root = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(self.root)
        # models that face +Y get turned around by an intermediate empty, leaving the
        # armature's own (glTF up-axis) transform untouched
        self.facing = bpy.data.objects.new(name + ".facing", None)
        bpy.context.scene.collection.objects.link(self.facing)
        self.facing.parent = self.root
        self.facing.rotation_euler = (0, 0, 0 if faces_neg_y else math.pi)
        self.arm.parent = self.facing
        if self.arm.animation_data:
            self.arm.animation_data.action = None
        else:
            self.arm.animation_data_create()
        for pb in self.arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        self.name = name
        self.scales = {}
        self.update()
        # rest-pose "face forward" expressed in the Head bone's local frame
        self.rest_reset()
        hb = self.pb("Head")
        self._head_fwd_local = (self.bone_world(hb).to_3x3().inverted() @ self.char_to_world_dir(v(0, -1, 0)))

    # -- lookup / transforms ------------------------------------------------
    def pb(self, short):
        return self.arm.pose.bones[P + short]

    def has(self, short):
        return (P + short) in self.arm.pose.bones

    def update(self):
        bpy.context.view_layer.update()

    def bone_world(self, pb):
        return self.arm.matrix_world @ pb.matrix

    def joint(self, short):
        return (self.arm.matrix_world @ self.pb(short).head).copy()

    def char_to_world_dir(self, d):
        return (self.root.matrix_world.to_3x3() @ Vector(d)).normalized()

    def set_bone_world(self, pb, mw):
        pb.matrix = self.arm.matrix_world.inverted() @ mw
        self.update()

    def rotate_world(self, pb, q):
        """Rotate a pose bone by world-space quaternion q about its head."""
        mw = self.bone_world(pb)
        head = mw.translation.copy()
        rot = q.to_matrix().to_4x4()
        new = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ mw
        self.set_bone_world(pb, new)

    # -- posing ----------------------------------------------------------------
    def rest_reset(self):
        for pb in self.arm.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = Vector()
            pb.scale = Vector(self.scales.get(pb.name[len(P):], (1, 1, 1)))
        self.update()

    def aim(self, short, d_char):
        pb = self.pb(short)
        a, b = self.joint(short), self.joint(CHILD[short])
        cur = (b - a).normalized()
        tgt = self.char_to_world_dir(d_char)
        self.rotate_world(pb, cur.rotation_difference(tgt))

    def aim_world(self, short, d_world):
        pb = self.pb(short)
        a, b = self.joint(short), self.joint(CHILD[short])
        self.rotate_world(pb, (b - a).normalized().rotation_difference(Vector(d_world).normalized()))

    def ik_arm(self, side, target, pole, hand_dir=None):
        """Two-bone IK: put the wrist of `side` ('Left'/'Right') on world point `target`,
        elbow bending toward world direction `pole`."""
        S = self.joint(f"{side}Arm")
        L1 = (self.joint(f"{side}ForeArm") - S).length
        L2 = (self.joint(f"{side}Hand") - self.joint(f"{side}ForeArm")).length
        T = Vector(target)
        d = min((T - S).length, (L1 + L2) * 0.999)
        u = (T - S).normalized()
        T = S + u * d
        a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        p = Vector(pole) - u * Vector(pole).dot(u)
        p = p.normalized() if p.length > 1e-6 else Vector((0, 0, -1))
        E = S + u * a + p * h
        self.aim_world(f"{side}Arm", E - S)
        self.aim_world(f"{side}ForeArm", T - self.joint(f"{side}ForeArm"))
        if hand_dir is not None:
            self.aim_world(f"{side}Hand", hand_dir)

    def twist(self, short, deg):
        """Roll a segment about its own axis (positive = right-hand rule)."""
        pb = self.pb(short)
        a, b = self.joint(short), self.joint(CHILD[short])
        self.rotate_world(pb, Quaternion((b - a).normalized(), math.radians(deg)))

    def look(self, d_char, up_char=(0, 0, 1)):
        """Point the face of the Head bone along d_char (keeps the head upright-ish)."""
        pb = self.pb("Head")
        fwd = (self.bone_world(pb).to_3x3() @ self._head_fwd_local).normalized()
        tgt = self.char_to_world_dir(d_char)
        self.rotate_world(pb, fwd.rotation_difference(tgt))

    def pose(self, spec, hips=(0, 0, 0), hips_tilt=0.0):
        """spec: {segment: direction | ('twist', deg)} applied root-first.
        hips: world-ish offset of the Hips (character space, metres).
        hips_tilt: forward pitch of the pelvis in degrees."""
        self.rest_reset()
        hp = self.pb("Hips")
        if hips_tilt:
            axis = self.char_to_world_dir(v(1, 0, 0))
            self.rotate_world(hp, Quaternion(axis, math.radians(hips_tilt)))
        if any(hips):
            mw = self.bone_world(hp)
            mw.translation += self.root.matrix_world.to_3x3() @ Vector(hips)
            self.set_bone_world(hp, mw)
        order = ["Spine", "Spine1", "Spine2", "Neck", "Head",
                 "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
                 "RightShoulder", "RightArm", "RightForeArm", "RightHand",
                 "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"]
        for seg in order:
            if seg == "Head":
                if "look" in spec:
                    self.look(spec["look"])
                continue
            if seg in spec:
                self.aim(seg, spec[seg])
            if seg + ".twist" in spec:
                self.twist(seg, spec[seg + ".twist"])
        fingers = spec.get("fingers")
        if fingers is not None:
            self.curl_fingers(fingers)

    def curl_fingers(self, amount, side=("Left", "Right")):
        """0 = straight, 1 = fist (rotates finger joints about the hand's lateral axis)."""
        for s in side:
            hand = self.pb(f"{s}Hand")
            hw = self.bone_world(hand)
            for f in ("Index", "Middle", "Ring", "Pinky"):
                for j in (1, 2, 3):
                    n = f"{s}Hand{f}{j}"
                    if not self.has(n):
                        continue
                    pb = self.pb(n)
                    # lateral axis = across the knuckles
                    a = self.joint(f"{s}HandIndex1") if self.has(f"{s}HandIndex1") else hw.translation
                    b = self.joint(f"{s}HandPinky1") if self.has(f"{s}HandPinky1") else hw.translation
                    axis = (b - a).normalized() if s == "Left" else (a - b).normalized()
                    self.rotate_world(pb, Quaternion(axis, math.radians(-70 * amount)))

    def key(self, frame):
        for pb in self.arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        self.pb("Hips").keyframe_insert("location", frame=frame)

    def key_pose(self, frame, spec, **kw):
        self.pose(spec, **kw)
        self.key(frame)

    def play_action(self, name_prefix):
        act = next(a for a in bpy.data.actions if a.name.startswith(name_prefix))
        self.arm.animation_data.action = act
        return act

    def proportions(self, scales):
        """Per-bone (x, length, z) scale for uncanny proportions; children keep their own scale."""
        for b in self.arm.data.bones:
            b.inherit_scale = "NONE"
        self.scales = dict(scales)
        self.rest_reset()

    def material(self, mat):
        for m in self.meshes:
            m.data.materials.clear()
            m.data.materials.append(mat)
            for poly in m.data.polygons:
                poly.material_index = 0


# -- materials ----------------------------------------------------------------
def principled(name, color, rough=0.6, sss=0.0, sss_radius=(0.1, 0.05, 0.04), emission=None, metallic=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Specular IOR Level"].default_value = spec
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = sss_radius
    if emission:
        b.inputs["Emission Color"].default_value = (*emission[0], 1)
        b.inputs["Emission Strength"].default_value = emission[1]
    return m


def noise_material(name, c1, c2, scale=8.0, rough=0.8, bump=0.2, detail=6.0, distortion=0.0, coord="Object"):
    """Two-colour noise texture material with matching bump."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nz.inputs["Distortion"].default_value = distortion
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(tc.outputs[coord], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


def tile_material(name, tile=(0.82, 0.83, 0.8), grout=(0.35, 0.36, 0.34), scale=6.0, dirt=0.35, rough=0.35,
                  axes=("X", "Y")):
    """Bathroom-style wall tiles (brick texture with zero offset) with grime."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.5
    br.inputs["Color1"].default_value = (*tile, 1)
    br.inputs["Color2"].default_value = (*tile, 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 8.0
    grime = nt.nodes.new("ShaderNodeValToRGB")
    grime.color_ramp.elements[0].position = 0.3
    grime.color_ramp.elements[0].color = (0.25, 0.24, 0.2, 1)
    grime.color_ramp.elements[1].position = 0.7
    grime.color_ramp.elements[1].color = (1, 1, 1, 1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = dirt
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.3
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nt.links.new(sep.outputs[axes[0]], comb.inputs["X"])
    nt.links.new(sep.outputs[axes[1]], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], br.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(br.outputs["Color"], mix.inputs["A"])
    nt.links.new(nz.outputs["Fac"], grime.inputs["Fac"])
    nt.links.new(grime.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


# -- geometry ----------------------------------------------------------------
def box(name, size, loc, mat=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        o.data.materials.append(mat)
    return o


def plane(name, size, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        o.data.materials.append(mat)
    return o


def area_light(name, loc, rot, size, energy, color=(1, 1, 1), shape="RECTANGLE", size_y=None):
    l = bpy.data.lights.new(name, "AREA")
    l.energy = energy
    l.color = color
    l.shape = shape
    l.size = size
    if size_y:
        l.size_y = size_y
    o = bpy.data.objects.new(name, l)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.scene.collection.objects.link(o)
    return o


def point_light(name, loc, energy, color=(1, 1, 1), radius=0.05, kind="POINT", spot=None):
    l = bpy.data.lights.new(name, kind)
    l.energy = energy
    l.color = color
    l.shadow_soft_size = radius
    if spot:
        l.spot_size = math.radians(spot)
        l.spot_blend = 0.6
    o = bpy.data.objects.new(name, l)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


def camera(name, loc, look_at, lens=24.0, sensor=36.0):
    c = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    c.data.lens = lens
    c.data.sensor_width = sensor
    c.location = loc
    d = Vector(look_at) - Vector(loc)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(c)
    return c


def world(color=(0.0, 0.0, 0.0), strength=1.0):
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength
    return w


def render_settings(res=(960, 720), samples=48, fps=15, exposure=0.0, look="AgX - Medium High Contrast",
                    denoise=True, threads=4):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = denoise
    sc.cycles.max_bounces = 4
    sc.cycles.adaptive_threshold = 0.03
    sc.render.use_persistent_data = True
    sc.render.threads_mode = "FIXED"
    sc.render.threads = threads
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    sc.view_settings.exposure = exposure
    return sc


def fcurves_of(obj, data=False):
    ad = (obj.data if data else obj).animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
    return list(cb.fcurves) if cb else []


def set_interpolation(obj, kind="LINEAR", data=False):
    for fc in fcurves_of(obj, data):
        for kp in fc.keyframe_points:
            kp.interpolation = kind


def screen_pos(cam, world_pt):
    """Normalized (x, y) with origin top-left, plus depth."""
    from bpy_extras.object_utils import world_to_camera_view
    p = world_to_camera_view(bpy.context.scene, cam, Vector(world_pt))
    return [round(p.x, 5), round(1 - p.y, 5), round(p.z, 4)]


def head_box(ch, cam):
    """Screen-space box around a character's head (for censor bars / tracking)."""
    bpy.context.view_layer.update()
    head = ch.joint("Head")
    top = ch.joint("HeadTop_End") if ch.has("HeadTop_End") else head + Vector((0, 0, 0.2))
    mid = (ch.joint("Head") + top) / 2
    r = (top - ch.joint("Head")).length * 0.75
    pts = [mid + Vector(o) * r for o in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1.2)]]
    sp = [screen_pos(cam, p) for p in pts]
    xs, ys = [p[0] for p in sp], [p[1] for p in sp]
    return [min(xs), min(ys), max(xs), max(ys)]


def out_dir(name):
    d = RENDERS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=1))
