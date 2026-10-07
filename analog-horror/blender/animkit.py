"""Write dense animation curves from numpy arrays (fast, frame-accurate) + easing helpers."""
import numpy as np
import bpy

FPS = 30


def fr(t):
    return t * FPS + 1.0


def ease(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x < 0.5, 4 * x ** 3, 1 - (-2 * x + 2) ** 3 / 2)


def _fcurves(action):
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def curve(id_block, data_path, index=-1, owner=None):
    """Return (creating if needed) the fcurve animating `data_path` on `id_block`.
    `owner` is the struct whose keyframe_insert creates it (defaults to id_block)."""
    owner = owner or id_block
    ad = id_block.animation_data or id_block.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{id_block.name}_act")
    act = ad.action
    for fc in _fcurves(act):
        if fc.data_path == data_path and (index < 0 or fc.array_index == index):
            return fc
    prop = data_path.rsplit(".", 1)[-1] if owner is not id_block else data_path
    owner.keyframe_insert(prop, index=index, frame=1)
    for fc in _fcurves(act):
        if fc.data_path == data_path and (index < 0 or fc.array_index == max(index, 0)):
            return fc
    raise RuntimeError(f"fcurve not created for {data_path}")


def write(fc, frames, values, interp="LINEAR"):
    frames = np.asarray(frames, dtype=np.float32)
    values = np.asarray(values, dtype=np.float32)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    co = np.empty(len(frames) * 2, dtype=np.float32)
    co[0::2], co[1::2] = frames, values
    fc.keyframe_points.foreach_set("co", co)
    ip = {"LINEAR": 1, "CONSTANT": 0, "BEZIER": 2}[interp]
    fc.keyframe_points.foreach_set("interpolation", np.full(len(frames), ip, dtype=np.int32))
    fc.update()


def key_series(id_block, data_path, frames, values, index=-1, owner=None, interp="LINEAR"):
    write(curve(id_block, data_path, index, owner), frames, values, interp)


def piecewise(keys, t, mode="smooth"):
    """keys: list of (time, value); smooth (eased) or linear interpolation, held at ends."""
    keys = sorted(keys)
    ts = np.array([k[0] for k in keys])
    vs = np.array([k[1] for k in keys], dtype=float)
    out = np.empty_like(t, dtype=float)
    out[:] = vs[0]
    for i in range(len(keys) - 1):
        a, b = ts[i], ts[i + 1]
        m = (t >= a) & (t <= b)
        x = (t[m] - a) / max(b - a, 1e-6)
        if mode == "smooth":
            x = ease_io(x)
        out[m] = vs[i] + (vs[i + 1] - vs[i]) * x
    out[t > ts[-1]] = vs[-1]
    return out


def visibility(obj, intervals, t_end_frame):
    """Keyframe hide_render/hide_viewport so obj is visible only inside [t0, t1) intervals."""
    frames, vals = [1], [1.0]
    for t0, t1 in intervals:
        frames += [fr(t0), fr(t1)]
        vals += [0.0, 1.0]
    for prop in ("hide_render", "hide_viewport"):
        setattr(obj, prop, True)
        obj.keyframe_insert(prop, frame=1)
        fc = curve(obj, prop)
        write(fc, frames, vals, "CONSTANT")
