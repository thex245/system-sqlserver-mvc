"""Retarget sanity test: seated idle clips on the two leads; renders side/front views and prints
contact metrics (hand/pelvis/foot heights) used to size chairs and tables."""
import os, sys
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import rbx, anim

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 640, 480
sc.render.fps = 30

pairs = [("Business_Male_01", "m_sit_table_idle_neutral_01", -0.8), ("Female_Adult_11", "f_sit_table_breathe_01", 0.8)]
for name, clip, x in pairs:
    arm, mesh = rbx.import_avatar(name)
    act = anim.bake_clip(arm, clip, frames=(1, 90))
    arm.animation_data_create()
    arm.animation_data.action = act
    arm.location.x = x
    sc.frame_set(45)
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    def wp(b, tail=False):
        pb = arm.pose.bones[b]
        return mw @ (pb.tail if tail else pb.head)
    print("METRIC", name, "scale", tuple(arm.scale), "pelvis", tuple(round(v, 3) for v in wp("Bip01 Pelvis")),
          "Lhand", tuple(round(v, 3) for v in wp("Bip01 L Hand")), "Rhand", tuple(round(v, 3) for v in wp("Bip01 R Hand")),
          "Lfoot", tuple(round(v, 3) for v in wp("Bip01 L Foot")), "Ltoe", tuple(round(v, 3) for v in wp("Bip01 L Toe0", True)),
          "Lthigh", tuple(round(v, 3) for v in wp("Bip01 L Thigh")), "Lcalf", tuple(round(v, 3) for v in wp("Bip01 L Calf")))
    # lowest mesh point at seat / hands (evaluated mesh)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg)
    zs = [(ev.matrix_world @ v.co) for v in ev.data.vertices]
    print("METRIC", name, "mesh minZ", round(min(p.z for p in zs), 3), "minY", round(min(p.y for p in zs), 3),
          "maxY", round(max(p.y for p in zs), 3))

# Floor + light + cameras
bpy.ops.mesh.primitive_plane_add(size=6)
l = bpy.data.lights.new("sun", "SUN"); l.energy = 3
lo = bpy.data.objects.new("sun", l); sc.collection.objects.link(lo); lo.rotation_euler = (0.7, 0.2, 0.5)
w = bpy.data.worlds.new("w"); w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.3, 0.32, 1); sc.world = w
for label, loc, rot in [("side", (4.0, 0.0, 0.8), (1.5708, 0, 1.5708)), ("front", (0.0, -4.0, 0.9), (1.5708, 0, 0))]:
    cd = bpy.data.cameras.new(label); cd.lens = 35
    co = bpy.data.objects.new(label, cd); sc.collection.objects.link(co)
    co.location, co.rotation_euler = loc, rot
    sc.camera = co
    sc.render.filepath = os.path.join(out, f"retarget_{label}.png")
    bpy.ops.render.render(write_still=True)
