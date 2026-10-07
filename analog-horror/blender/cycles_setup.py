"""Switch the open scene to Cycles on the NVIDIA GPU (OptiX) with CCTV-appropriate settings."""
import os
import bpy


def setup(samples=None):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                print("cycles: using", backend, [d.name for d in gpus])
                break
        except TypeError:
            continue
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    sc.cycles.samples = int(samples or os.environ.get("VAMA_SAMPLES", "96"))
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPTIX"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.cycles.texture_limit_render = os.environ.get("VAMA_CY_TEXLIMIT", "2048")
    sc.render.use_persistent_data = True
    sc.cycles.use_light_tree = True
    return sc


if __name__ == "__main__":
    setup()
