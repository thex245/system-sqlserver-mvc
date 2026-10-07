"""Render test stills: blender -b film.blend --python render_test.py -- OUT_DIR spec [spec ...]
spec = "t:lens:tx,ty,tz[:name]" (film seconds, focal mm, look-at target). lens 0 = use the scene's CAM04."""
import os, sys
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import lowmem  # noqa: F401
from layout import CAM_POS
if os.environ.get("VAMA_ENGINE", "eevee") == "cycles":
    import cycles_setup
    cycles_setup.setup()

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
cam = bpy.data.objects.get("CAM04_test")
if cam is None:
    cd = bpy.data.cameras.new("CAM04_test")
    cd.sensor_width = 36
    cam = bpy.data.objects.new("CAM04_test", cd)
    sc.collection.objects.link(cam)
for spec in a[1:]:
    parts = spec.split(":")
    t, lens = float(parts[0]), float(parts[1])
    name = parts[3] if len(parts) > 3 else f"t{t:06.2f}_l{int(lens)}"
    sc.frame_set(int(round(t * 30)) + 1)
    if lens > 0:
        tgt = Vector(tuple(map(float, parts[2].split(","))))
        cam.data.lens = lens
        cam.location = CAM_POS
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
    else:
        sc.camera = bpy.data.objects["CAM04"]
    sc.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", sc.render.filepath)
