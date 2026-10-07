"""Animation review renders of the hero performance (same assets/animation as the film), keeping only
what CAM 04 sees around the couple's table so it fits in limited memory.

blender -b --gpu-backend vulkan film.blend --python review_scene.py -- OUT_DIR t0 t1 [t0 t1 ...]
"""
import os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import lowmem  # noqa: F401
from layout import COUPLE_TABLE
from timeline import FPS

a = sys.argv[sys.argv.index("--") + 1:]
OUT = a[0]
ranges = [(float(a[i]), float(a[i + 1])) for i in range(1, len(a) - 1, 2)]
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
C = Vector(COUPLE_TABLE[:2])
keep_tags = ("man_", "woman_", "chair_man", "chair_woman", "couple", "lens", "CAM04", "pendant_light_0",
             "man_ring", "woman_ring", "kdoor", "blood")
removed = 0
for o in list(bpy.data.objects):
    name = o.name
    if name.startswith(keep_tags) or name.startswith(("floor", "ceiling", "wall_", "glass_", "winframe", "mullion",
                                                      "transom", "rail_", "crown_", "base_", "beam_", "street",
                                                      "sidewalk", "curb", "facade", "fwin", "streetlamp", "car_light",
                                                      "fill_room", "sconce_light")):
        continue
    if o.type in ("MESH", "EMPTY", "LIGHT", "ARMATURE", "CURVE", "FONT"):
        # keep anything within 2.2 m of the couple's table (props, chairs, plant, window furniture)
        p = o.matrix_world.translation
        if (Vector((p.x, p.y)) - C).length < 2.2 and not name.endswith(("_body", "_rig", "_root")):
            continue
        if o.parent and o.parent.name.startswith(keep_tags):
            continue
        bpy.data.objects.remove(o, do_unlink=True)
        removed += 1
print("REVIEW removed", removed, "objects; kept", len(bpy.data.objects))
sc.camera = bpy.data.objects["CAM04"]
for t0, t1 in ranges:
    for f in range(int(t0 * FPS) + 1, int(t1 * FPS) + 1):
        p = os.path.join(OUT, f"r_{f:05d}.png")
        if os.path.exists(p):
            continue
        sc.frame_set(f)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print("REVIEW", f, flush=True)
