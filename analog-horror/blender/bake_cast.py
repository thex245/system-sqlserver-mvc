"""Bake the body clips for one or more cast members into D:\\VAMA_work\\blend\\chars\\<tag>.blend

blender -b --factory-startup --python bake_cast.py -- OUT_DIR tag [tag ...]
Each file holds the avatar (rig + mesh + materials) and its baked actions named '<tag>:<clip>'
with custom props lo/hi = baked clip frame range (action frame 1 == clip frame lo).
"""
import os, sys, time
import bpy
sys.path.insert(0, os.path.dirname(__file__))
import rbx, anim
from cast import BY_TAG, needed_clip_ranges, WAITER

args = sys.argv[sys.argv.index("--") + 1:]
out_dir, tags = args[0], args[1:]
os.makedirs(out_dir, exist_ok=True)
for tag in tags:
    t_start = time.time()
    c = BY_TAG[tag]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    arm, mesh = rbx.import_avatar(c["avatar"], facial=True, tag=tag)
    step = 1                      # full density for everyone (renders at 30 fps)
    if tag == "waiter":
        longest = max(w["t1"] - w["t0"] for w in WAITER["walks"])
        ncyc = int(longest * 30 / 32) + 2
        act = anim.bake_clip(arm, "m_walk_neutral", step=1, cycles=ncyc, action_name="waiter:walk")
        act["lo"], act["hi"] = 1, 1 + 32 * ncyc
        print("BAKED", tag, "walk cycles", ncyc)
    else:
        for clip, (lo, hi) in needed_clip_ranges(c).items():
            act = anim.bake_clip(arm, clip, frames=(lo, hi), step=step, action_name=f"{tag}:{clip}")
            act["lo"], act["hi"] = lo, hi
            print("BAKED", tag, clip, lo, hi, f"{time.time() - t_start:.0f}s", flush=True)
    if arm.animation_data:
        arm.animation_data.action = None
    for o in list(bpy.data.objects):
        if o not in (arm, mesh):
            bpy.data.objects.remove(o, do_unlink=True)
    path = os.path.join(out_dir, f"{tag}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("SAVED", path, f"{time.time() - t_start:.0f}s", flush=True)
