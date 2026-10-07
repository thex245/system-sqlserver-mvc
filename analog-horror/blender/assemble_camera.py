"""CAM 04: a corner PTZ dome that zooms and auto-tracks on its own. Runs in assemble.py's namespace."""

cd = bpy.data.cameras.new("CAM04")
cd.sensor_width = 36.0
cd.clip_start, cd.clip_end = 0.05, 120.0
CAM = bpy.data.objects.new("CAM04", cd)
sc.collection.objects.link(CAM)
CAM.location = CAM_POS
sc.camera = CAM


def wpos(obj, t, off=(0, 0, 0)):
    sc.frame_set(int(K.fr(t)))
    bpy.context.view_layer.update()
    return obj.matrix_world.translation + Vector(off)


def mid(a, b, dz=0.0):
    return (a + b) / 2 + Vector((0, 0, dz))


class Track:
    """Camera target that follows an object (auto-track)."""
    def __init__(self, obj, off=(0, 0, 0), obj2=None):
        self.obj, self.off, self.obj2 = obj, Vector(off), obj2


WIDE = Vector(CAM_TARGET_WIDE)
WIDE2 = Vector((5.6, 6.2, 0.75))
TABLE_T = C3 + Vector((0.05, 0.25, 0.55))
TWO = mid(wpos(W_FACE, 47.0), wpos(M_FACE, 47.0), -0.12)
TWO_S = mid(wpos(W_FACE, 82.0), wpos(M_FACE, 82.0), -0.18)
TWO_S4 = mid(wpos(W_FACE, 108.0), wpos(M_FACE, 108.0), -0.12)
M_CHEST = wpos(M_FACE, 100.0, (0, 0, -0.32))
WF = Track(W_FACE, (0, 0, -0.03))
WH = Track(W_HAND, (0, 0, 0.02))
WFH = Track(W_FACE, (0, 0, 0.0), obj2=W_HAND)     # her face and the raised hand together
ML = Track(L_TGT, (0, 0, 0.0))

PLAN = {
    "establish": [(3.0, WIDE, 20.0), (SEG["establish"][2], WIDE, 23.5, "linear")],
    "dialogue": [(41.0, WIDE, 20.0), (42.5, WIDE, 20.0), (46.5, TWO, 150.0), (52.3, TWO, 150.0),
                 (56.8, WF, 430.0), (58.8, WF, 430.0), (60.3, WH, 520.0), (64.9, WH, 520.0),
                 (67.0, WFH, 330.0), (SPEAK["W03"] + 0.4, WFH, 330.0), (SPEAK["W03"] + 1.8, WF, 470.0),
                 (SEG["dialogue"][2], WF, 470.0)],
    "standing": [(79.5, TWO_S, 120.0), (85.9, TWO_S, 120.0), (89.0, WIDE2, 32.0), (SEG["standing"][2], WIDE2, 32.0)],
    "ring": [(99.5, M_CHEST, 260.0), (100.7, ML, 560.0), (T_PULL1 + 0.2, ML, 560.0), (T_DROP + 0.1, DROP_PT, 480.0),
             (T_DROP + 0.8, RING_REST, 540.0), (106.4, TWO_S4, 160.0), (107.4, WF, 420.0), (110.9, WF, 420.0),
             (111.7, TWO_S4, 140.0), (113.3, TWO_S4, 140.0), (FREEZE_AT, WF, 290.0)],
    "empty": [(121.5, WIDE, 20.0), (125.5, WIDE, 20.0), (133.5, TABLE_T, 170.0), (139.3, TABLE_T, 170.0),
              (143.3, WF, 520.0), (SEG["empty"][2], WF, 600.0)],
}


def resolve(target, t):
    if not isinstance(target, Track):
        return Vector(target)
    p = wpos(target.obj, t, target.off)
    if target.obj2 is not None:                     # frame two things: midpoint
        p = (p + wpos(target.obj2, t, target.off)) / 2
    return p


tgt = np.zeros((len(TT), 3))
lens = np.full(len(TT), 20.0)
for seg, keys in PLAN.items():
    a, b = SEG[seg][1], SEG[seg][2]
    idx = np.where((TT >= a) & (TT < b))[0]
    # sample targets (tracked targets every 4 frames)
    pos = np.zeros((len(idx), 3))
    lz = np.zeros(len(idx))
    for j in range(len(keys) - 1):
        k0, k1 = keys[j], keys[j + 1]
        t0, t1 = k0[0], k1[0]
        m = (TT[idx] >= t0) & (TT[idx] <= t1)
        if not m.any():
            continue
        x = (TT[idx][m] - t0) / max(t1 - t0, 1e-6)
        x = x if (len(k1) > 3 and k1[3] == "linear") else K.ease_io(x)
        sub = idx[m]
        P0_ = np.array([resolve(k0[1], t) for t in TT[sub][::4]])
        P1_ = np.array([resolve(k1[1], t) for t in TT[sub][::4]])
        P0_ = np.array([np.interp(np.arange(len(sub)), np.arange(0, len(sub), 4)[:len(P0_)], P0_[:, i]) for i in range(3)]).T
        P1_ = np.array([np.interp(np.arange(len(sub)), np.arange(0, len(sub), 4)[:len(P1_)], P1_[:, i]) for i in range(3)]).T
        pos[m] = P0_ + (P1_ - P0_) * x[:, None]
        lz[m] = np.exp(np.log(k0[2]) + (np.log(k1[2]) - np.log(k0[2])) * x)
    last = keys[-1]
    m = TT[idx] > last[0]
    if m.any():
        pos[m] = np.array([resolve(last[1], last[0])] * m.sum())
        lz[m] = last[2]
    # PTZ servo: first-order lag on pan/tilt and zoom (restarted at every cut)
    alpha = 1 - math.exp(-1.0 / (FPS * 0.16))
    for i in range(1, len(idx)):
        pos[i] = pos[i - 1] + (pos[i] - pos[i - 1]) * alpha
        lz[i] = lz[i - 1] + (lz[i] - lz[i - 1]) * alpha
    tgt[idx], lens[idx] = pos, lz
# hold the last picture through the freeze
fz = (TT >= FREEZE_AT) & (TT < SEG["empty"][1])
i_fz = np.searchsorted(TT, FREEZE_AT) - 1
tgt[fz], lens[fz] = tgt[i_fz], lens[i_fz]
tgt[TT < 3.0] = WIDE
tgt[TT >= SEG["end"][1]] = tgt[np.searchsorted(TT, SEG["end"][1]) - 1]
lens[TT >= SEG["end"][1]] = lens[np.searchsorted(TT, SEG["end"][1]) - 1]
# tiny mechanical jitter that grows with zoom
jit = np.random.default_rng(8).normal(0, 1, (len(TT), 2))
jit = np.apply_along_axis(lambda v: np.convolve(v, np.ones(6) / 6, "same"), 0, jit) * 0.00035 * (lens[:, None] / 100.0)
eul = np.zeros((len(TT), 3))
cp = Vector(CAM_POS)
for i in range(len(TT)):
    q = (Vector(tgt[i]) - cp).to_track_quat("-Z", "Y")
    e = q.to_euler()
    eul[i] = (e.x + jit[i, 0], e.y, e.z + jit[i, 1])
eul[:, 2] = np.unwrap(eul[:, 2])
CAM.rotation_mode = "XYZ"
for i in range(3):
    K.key_series(CAM, "rotation_euler", FRAMES, eul[:, i], index=i)
K.key_series(cd, "lens", FRAMES, lens)
np.save(os.path.join(os.path.dirname(OUT), "cam_lens.npy"), lens)   # OSD zoom readout in post
print("PERF camera done", flush=True)

# ======================================================================================== render settings
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 64
sc.eevee.shadow_pool_size = "2048"
sc.render.resolution_x, sc.render.resolution_y = 1280, 960
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.image_settings.compression = 15
sc.render.use_motion_blur = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast"
