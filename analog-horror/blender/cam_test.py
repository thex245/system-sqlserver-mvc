"""Open a .blend, add CAM 04 and render a still: blender -b file.blend --python cam_test.py -- out.png [lens] [tx ty tz]"""
import sys, os
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from layout import CAM_POS

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
lens = float(a[1]) if len(a) > 1 else 20.0
tgt = Vector(tuple(map(float, a[2:5]))) if len(a) > 4 else Vector((4.3, 6.4, 0.6))
sc = bpy.context.scene
cd = bpy.data.cameras.new("CAM04")
cd.lens = lens
cd.sensor_width = 36
cam = bpy.data.objects.new("CAM04", cd)
sc.collection.objects.link(cam)
cam.location = CAM_POS
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
