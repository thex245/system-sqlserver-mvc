"""Resumable film render (Eevee, every film frame at 30 fps).

blender -b --gpu-backend vulkan film.blend --python render_film.py -- OUT_DIR [t0 t1] [--freeze FREEZE_DIR]
Frames already on disk are skipped, so the render can be stopped and restarted at any time.
The freeze segment is rendered separately (--freeze): time stays at FREEZE_AT while her face is
pulled toward the lens by a Warp deformer; face.json stores its screen position for the 2D pass.
"""
import json, math, os, sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import lowmem  # noqa: F401
from timeline import SEG, FREEZE_AT, FPS

a = sys.argv[sys.argv.index("--") + 1:]
OUT = a[0]
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
cam = bpy.data.objects["CAM04"]
sc.camera = cam


def render_frame(f, path):
    sc.frame_set(f)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if "--freeze" not in a:
    t0 = float(a[1]) if len(a) > 1 else SEG["establish"][1]
    t1 = float(a[2]) if len(a) > 2 else SEG["end"][1]
    live = [(SEG[s][1], SEG[s][2]) for s in ("establish", "dialogue", "standing", "ring", "empty")]
    n = 0
    for f in range(int(t0 * FPS) + 1, int(t1 * FPS) + 1):
        t = (f - 1) / FPS
        if not any(x <= t < y for x, y in live):
            continue
        p = os.path.join(OUT, f"f_{f:05d}.png")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            continue
        render_frame(f, p)
        n += 1
        print(f"FRAME {f} t={t:.2f}", flush=True)
    print("DONE", n)
else:
    fdir = a[a.index("--freeze") + 1]
    os.makedirs(fdir, exist_ok=True)
    F = int(FREEZE_AT * FPS) + 1 - 1          # last live frame
    sc.frame_set(F)
    wm = bpy.data.objects["woman_body"]
    wa = bpy.data.objects["woman_rig"]
    face = bpy.data.objects["woman_face"]
    pf = face.matrix_world.translation.copy()
    # screen position + size of her face for the 2D pass
    co = world_to_camera_view(sc, cam, pf)
    co2 = world_to_camera_view(sc, cam, pf + Vector((0, 0, 0.12)))
    json.dump({"x": co.x, "y": 1 - co.y, "r": abs(co2.y - co.y)}, open(os.path.join(fdir, "face.json"), "w"))
    # vertex group: everything driven by the head and facial bones
    vg = wm.vertex_groups.get("pull") or wm.vertex_groups.new(name="pull")
    head_groups = {g.index for g in wm.vertex_groups if g.name == "Bip01 Head" or
                   (g.name.startswith("Bip01 ") and any(k in g.name for k in ("Eye", "Jaw", "Lip", "Mouth", "Cheek",
                                                                                "brow", "Brow", "Nose", "Caninus", "Masseter")))}
    for v in wm.data.vertices:
        w = sum(g.weight for g in v.groups if g.group in head_groups)
        if w > 0.05:
            vg.add([v.index], min(1.0, w), "REPLACE")
    src = bpy.data.objects.new("pull_from", None)
    dst = bpy.data.objects.new("pull_to", None)
    for o in (src, dst):
        sc.collection.objects.link(o)
    src.location = pf
    dst.location = pf
    mod = wm.modifiers.new("pull", "WARP")
    mod.object_from, mod.object_to = src, dst
    mod.vertex_group = "pull"
    mod.falloff_type = "SMOOTH"
    mod.falloff_radius = 0.16
    mod.strength = 1.0
    # keep the warp on top of the armature deform but before subdivision
    order = [m.name for m in wm.modifiers]
    if "subd" in order and order.index("pull") > order.index("subd"):
        with bpy.context.temp_override(object=wm):
            bpy.ops.object.modifier_move_to_index(modifier="pull", index=order.index("subd"))
    toward = (cam.matrix_world.translation - pf).normalized()
    nfr = int((SEG["empty"][1] - FREEZE_AT) * FPS)
    for k in range(nfr):
        p = os.path.join(fdir, f"z_{k:04d}.png")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            continue
        lt = k / FPS
        prog = max(0.0, min(1.0, (lt - 0.35) / 5.2))
        jit = 0.012 * math.sin(lt * 37.0) * prog
        dst.location = pf + toward * (0.42 * prog ** 1.6 + jit)
        mod.falloff_radius = 0.16 + 0.12 * prog
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"FREEZE {k}/{nfr}", flush=True)
    print("DONE freeze")
