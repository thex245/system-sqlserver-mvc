"""Low-memory Blender settings for this machine (small commit limit). Import before rendering."""
import os
import bpy

p = bpy.context.preferences.system
for attr, val in (("shader_compilation_method", "THREAD"), ("max_shader_compilation_subprocesses", 1),
                  ("gl_texture_limit", os.environ.get("VAMA_TEXLIMIT", "CLAMP_2048")), ("texture_collection_rate", 30),
                  ("texture_time_out", 60), ("use_gpu_subdivision", True)):
    if hasattr(p, attr):
        try:
            setattr(p, attr, val)
        except Exception as e:  # noqa: BLE001
            print("lowmem: cannot set", attr, e)
print("lowmem:", getattr(p, "shader_compilation_method", "?"), getattr(p, "gl_texture_limit", "?"))


def relink_images():
    """Textures converted .tga -> .png (downscaled) keep working."""
    import os
    n = 0
    for im in bpy.data.images:
        fp = bpy.path.abspath(im.filepath)
        if im.filepath and not os.path.exists(fp):
            alt = os.path.splitext(fp)[0] + ".png"
            if os.path.exists(alt):
                im.filepath = alt
                n += 1
    print("lowmem: relinked", n, "images")


relink_images()
