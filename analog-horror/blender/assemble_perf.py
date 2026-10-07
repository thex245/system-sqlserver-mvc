"""Performance layers, executed inside assemble.py's namespace (chars, K, S, np, TT, FRAMES ...).

faces (lip sync / expressions / blinks), gaze + head aims, hand IK (ring, slam), rings, props,
lights, blood, CAM 04 PTZ animation, render settings.
"""
import random
from mathutils import Quaternion

RNG = np.random.default_rng(4747)
LIP_LEAD = 2.0 / FPS        # visemes lead the audio by 2 frames (perceived sync)
LIPS = json.load(open(os.environ.get("VAMA_LIPSYNC", r"D:\VAMA_work\audio\lipsync.json")))
SEG_T = {k: (v[1], v[2]) for k, v in SEG.items()}
T_DIA, T_RING, T_EMPTY = SEG["dialogue"][1], SEG["ring"][1], SEG["empty"][1]
C3 = Vector(COUPLE_TABLE)
TOP = COUPLE_TOP_EFF


def env(keys, mode="smooth"):
    return K.piecewise(keys, TT, mode)


def pulse(t0, t1, ramp_in=0.4, ramp_out=0.4, peak=1.0):
    return env([(t0 - ramp_in, 0.0), (t0, peak), (t1, peak), (t1 + ramp_out, 0.0)])


# ======================================================================================== faces
AK = {"browDownL": "AK_01_BrowDownLeft", "browDownR": "AK_02_BrowDownRight", "browInnerUp": "AK_03_BrowInnerUp",
      "browOuterUpL": "AK_04_BrowOuterUpLeft", "browOuterUpR": "AK_05_BrowOuterUpRight",
      "cheekSquintL": "AK_07_CheekSquintLeft", "cheekSquintR": "AK_08_CheekSquintRight",
      "blinkL": "AK_09_EyeBlinkLeft", "blinkR": "AK_10_EyeBlinkRight", "squintL": "AK_19_EyeSquintLeft",
      "squintR": "AK_20_EyeSquintRight", "wideL": "AK_21_EyeWideLeft", "wideR": "AK_22_EyeWideRight",
      "jawOpen": "AK_25_JawOpen", "dimpleL": "AK_28_MouthDimpleLeft", "dimpleR": "AK_29_MouthDimpleRight",
      "frownL": "AK_30_MouthFrownLeft", "frownR": "AK_31_MouthFrownRight", "pressL": "AK_36_MouthPressLeft",
      "pressR": "AK_37_MouthPressRight", "smileL": "AK_44_MouthSmileLeft", "smileR": "AK_45_MouthSmileRight",
      "stretchL": "AK_46_MouthStretchLeft", "stretchR": "AK_47_MouthStretchRight",
      "upperUpL": "AK_48_MouthUpperUpLeft", "upperUpR": "AK_49_MouthUpperUpRight",
      "sneerL": "AK_50_NoseSneerLeft", "sneerR": "AK_51_NoseSneerRight", "shrugLower": "AK_42_MouthShrugLower",
      "lowerDownL": "AK_34_MouthLowerDownLeft", "lowerDownR": "AK_35_MouthLowerDownRight",
      "cheekRaise": "AU_06_CheekRaiser"}


def sym(**kw):
    out = {}
    for k, v in kw.items():
        if k + "L" in AK:
            out[k + "L"] = out[k + "R"] = v
        else:
            out[k] = v
    return out


PRESET = {
    # "a perfectly normal smile. Maybe too normal": mouth only, the eyes don't take part
    "smile_uncanny": sym(smile=0.62, cheekSquint=0.12, dimple=0.18, wide=0.06),
    "smile_sweet": sym(smile=0.78, cheekSquint=0.28, dimple=0.22, squint=0.06, browInnerUp=0.12),
    "confused": {**sym(browDown=0.18, press=0.12, squint=0.12), "browInnerUp": 0.6, "browDownL": 0.3,
                 "frownL": 0.12, "frownR": 0.05},
    "blank": sym(wide=0.14),
    "anxious": {**sym(press=0.22, wide=0.12, frown=0.12), "browInnerUp": 0.48},
    "fear": {**sym(wide=0.55, stretch=0.3, browOuterUp=0.35), "browInnerUp": 0.8},
    "tense": {**sym(browDown=0.55, sneer=0.15, press=0.3, squint=0.2)},
    "angry": {**sym(browDown=0.85, sneer=0.35, upperUp=0.22, squint=0.3, stretch=0.12)},
    "desperate": {**sym(browDown=0.25, frown=0.45, squint=0.25, stretch=0.18), "browInnerUp": 0.8},
    "rage": {**sym(browDown=1.0, sneer=0.6, upperUp=0.45, squint=0.35, stretch=0.3)},
}


class Face:
    def __init__(self, mesh):
        self.mesh = mesh
        self.key = mesh.data.shape_keys
        self.ch = {}

    def add(self, name, arr):
        self.ch[name] = self.ch.get(name, 0.0) + arr

    def expr(self, preset, weight_env):
        for k, v in PRESET[preset].items():
            self.add(AK[k], v * weight_env)

    def lips(self, line, t0, scale=0.85, jaw=0.15, stretch=0.0):
        L = LIPS[line]
        n = L["frames"]
        idx = np.arange(n)
        ft = t0 - LIP_LEAD + idx / FPS        # the mouth moves slightly before the sound is heard
        for name, vals in L["visemes"].items():
            arr = np.interp(TT, ft, np.array(vals) * scale, left=0.0, right=0.0)
            self.add(name, arr)
        e = np.interp(TT, ft, np.array(L["jaw"]), left=0.0, right=0.0)
        self.add(AK["jawOpen"], e * jaw)
        if stretch:
            self.add(AK["stretchL"], e * stretch)
            self.add(AK["stretchR"], e * stretch)

    def blinks(self, times, dur=0.16):
        """Real blinks close fast (~1/3) and reopen slower (~2/3)."""
        b = np.zeros_like(TT)
        for t in times:
            x = (TT - t) / dur
            m = (x >= 0) & (x <= 1)
            xm = x[m]
            shape = np.where(xm < 0.33, np.sin(np.pi / 2 * xm / 0.33), np.cos(np.pi / 2 * (xm - 0.33) / 0.67) ** 1.4)
            b[m] = np.maximum(b[m], shape)
        self.add(AK["blinkL"], b)
        self.add(AK["blinkR"], b)

    def write(self, step=1):
        sel = slice(None, None, step)
        for name, arr in self.ch.items():
            if name not in self.key.key_blocks:
                continue
            arr = np.clip(np.asarray(arr) * np.ones_like(TT), 0.0, 1.0)
            if arr.max() <= 1e-4:
                continue
            kb = self.key.key_blocks[name]
            K.key_series(self.key, f'key_blocks["{name}"].value', FRAMES[sel], arr[sel], owner=kb)


def blink_times(t0, t1, lo, hi, rng, avoid=()):
    out, t = [], t0 + rng.uniform(0, hi)
    while t < t1:
        if not any(a <= t <= b for a, b in avoid):
            out.append(t)
        t += rng.uniform(lo, hi)
    return out


SPEAK = {k: LINES[k] for k in LINES}
LINE_END = {k: LINES[k] + LIPS[k]["frames"] / FPS for k in LINES}

# ---- woman
WF = Face(chars["woman"][1])
smile = env([(0.0, 1.0), (BEATS["look_at_hand"] - 0.2, 1.0), (BEATS["look_at_hand"] + 0.6, 0.15),
             (SPEAK["W03"] - 0.3, 0.15), (SPEAK["W03"] + 0.6, 0.45), (BEATS["smile_off"] - 0.2, 0.45),
             (BEATS["smile_off"] + 1.3, 0.0), (BEATS["smile_back"], 0.0), (BEATS["smile_back"] + 1.9, 0.0)])
WF.expr("smile_uncanny", smile)
sweet = env([(BEATS["smile_back"], 0.0), (BEATS["smile_back"] + 1.9, 0.9), (BEATS["slam"], 0.9),
             (FREEZE_AT, 1.05), (FREEZE_AT + 0.2, 1.05)]) * (TT < T_EMPTY)
sweet += (TT >= BEATS["she_appears"]) * 0.95
WF.expr("smile_sweet", sweet)
WF.expr("confused", pulse(BEATS["look_at_hand"] + 0.2, SPEAK["W03"] - 0.2, 0.8, 1.2))
WF.expr("blank", env([(BEATS["smile_off"], 0.0), (BEATS["smile_off"] + 1.3, 1.0), (BEATS["smile_back"], 1.0),
                      (BEATS["smile_back"] + 1.5, 0.0)]))
for ln in ("W01", "W02", "W03", "W04", "W05", "W07"):
    WF.lips(ln, SPEAK[ln], scale=0.75, jaw=0.12)
# she never blinks... until the very end
WF.blinks([BEATS["final_blink"]], dur=0.75)

# ---- man
MF = Face(chars["man"][1])
MF.expr("anxious", env([(0.0, 0.75), (T_STAND - 0.1, 0.9), (T_STAND, 0.0)]))
MF.expr("fear", pulse(BEATS["man_looks_at_camera"] + 0.3, BEATS["man_looks_at_camera"] + 2.4, 0.5, 0.8, 0.7))
MF.expr("tense", pulse(SPEAK["M03"] - 0.3, LINE_END["M04"] + 2.0, 0.6, 1.5, 0.7))
MF.expr("angry", env([(T_STAND, 0.85), (SPEAK["M07"] - 0.5, 0.85), (SPEAK["M07"], 0.3), (T_RING, 0.3),
                      (SPEAK["M09"] - 0.2, 0.3), (SPEAK["M09"], 0.9), (BEATS["slam"], 0.9), (BEATS["slam"] + 0.15, 0.0)])
        * (TT >= T_STAND) * (TT < T_EMPTY))
MF.expr("desperate", env([(T_STAND, 0.0), (SPEAK["M07"] - 0.6, 0.0), (SPEAK["M07"], 0.9), (T_RING + 1, 0.8),
                          (SPEAK["M08"] + 1.5, 1.0), (SPEAK["M09"] - 0.3, 0.6), (SPEAK["M09"], 0.0)]) * (TT >= T_STAND))
MF.expr("rage", env([(BEATS["slam"] - 0.15, 0.0), (BEATS["slam"], 1.0), (FREEZE_AT + 1, 1.0)]) * (TT < T_EMPTY))
for ln in ("M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09"):
    MF.lips(ln, SPEAK[ln], scale=0.9, jaw=0.2)
MF.lips("M10", SPEAK["M10"], scale=1.0, jaw=0.6, stretch=0.35)
avoid = [(SPEAK["M10"], FREEZE_AT + 1)]
MF.blinks(blink_times(2.5, T_EMPTY, 2.2, 4.8, random.Random(5), avoid))   # + gaze-shift blinks below

# ---- extras: blinks + occasional chatter
for c in CAST:
    if c.get("hero") or c["tag"] == "waiter" or c["tag"] not in chars:
        continue
    mesh = chars[c["tag"]][1]
    if not mesh.data.shape_keys:
        continue
    F = Face(mesh)
    r = random.Random(sum(map(ord, c["tag"])))
    F.blinks(blink_times(2.5, T_EMPTY, 2.0, 5.5, r))
    talk = np.zeros_like(TT)
    t = r.uniform(3, 9)
    while t < T_EMPTY:
        d = r.uniform(1.5, 4.5)
        m = (TT > t) & (TT < t + d)
        talk[m] = 1.0
        t += d + r.uniform(3.0, 10.0)
    ph = r.uniform(0, 6)
    F.add("AA_VI_10_aa", talk * np.clip(0.45 * np.sin(TT * 13.0 + ph) + 0.1, 0, 1))
    F.add("AA_VI_13_O", talk * np.clip(0.35 * np.sin(TT * 9.0 + ph * 2), 0, 1))
    F.add("AA_VI_11_E", talk * np.clip(0.3 * np.sin(TT * 17.0 + ph * 3), 0, 1))
    F.add(AK["smileL"], 0.25 + 0.15 * np.sin(TT * 0.3 + ph))
    F.add(AK["smileR"], 0.25 + 0.15 * np.sin(TT * 0.3 + ph))
    F.write(step=1)


# ======================================================================================== gaze / head aims
def bone_empty(name, arm, bone, offset_world=(0, 0, 0), t=10.0):
    """Empty parented to a bone, placed at bone head + world offset (evaluated at film time t)."""
    sc.frame_set(int(K.fr(t)))
    e = bpy.data.objects.new(name, None)
    CH.objects.link(e)
    e.empty_display_size = 0.05
    e.parent = arm
    e.parent_type = "BONE"
    e.parent_bone = bone
    bpy.context.view_layer.update()
    head = arm.matrix_world @ arm.pose.bones[bone].head
    e.matrix_world = Matrix.Translation(head + Vector(offset_world))
    return e


def world_empty(name, loc):
    e = bpy.data.objects.new(name, None)
    CH.objects.link(e)
    e.empty_display_size = 0.08
    e.location = loc
    return e


def track(arm, bone, target, axis, name, influence_arr=None, const=1.0, step=1):
    pb = arm.pose.bones[bone]
    c = pb.constraints.new("DAMPED_TRACK")
    c.name = name
    c.target = target
    c.track_axis = axis
    c.influence = const
    if influence_arr is not None:
        sel = slice(None, None, step)
        K.key_series(arm, f'pose.bones["{bone}"].constraints["{name}"].influence', FRAMES[sel],
                     np.clip(influence_arr, 0, 1)[sel], owner=c)
    return c


MA, MM, _ = chars["man"]
WA, WM, _ = chars["woman"]
CAM_EMPTY = world_empty("lens", CAM_POS)
# Face targets hang off the neck (not the head) so the two heads tracking each other don't form a
# dependency cycle; the offset lands between the eyes at the time of placement.
def face_empty(name, arm, t):
    sc.frame_set(int(K.fr(t)))
    bpy.context.view_layer.update()
    pb = arm.pose.bones
    le = arm.matrix_world @ pb["Bip01 LEye"].head
    re = arm.matrix_world @ pb["Bip01 REye"].head
    e = bpy.data.objects.new(name, None)
    CH.objects.link(e)
    e.empty_display_size = 0.05
    e.parent, e.parent_type, e.parent_bone = arm, "BONE", "Bip01 Neck"
    bpy.context.view_layer.update()
    e.matrix_world = Matrix.Translation((le + re) / 2)
    return e


W_FACE = face_empty("woman_face", WA, 10.0)
M_FACE = face_empty("man_face", MA, 10.0)
W_HAND = bone_empty("woman_hand", WA, "Bip01 L Hand", (0, 0, 0.0))
M_HAND = bone_empty("man_hand", MA, "Bip01 L Hand", (0, 0, 0.0), t=T_RING + 2.0)
ROOM_LOOK = world_empty("man_room_look", (3.0, 6.0, 1.2))
# man's searching gaze wanders around the room (keyed path)
pts = [(2.0, (3.2, 8.3, 1.4)), (6.0, (2.0, 3.2, 1.2)), (9.5, (4.5, 9.0, 1.6)), (13.0, (6.6, 8.6, 1.3)),
       (17.0, (2.5, 6.0, 1.2)), (21.0, (4.6, 9.4, 1.6)), (24.0, (1.0, 4.4, 1.2))]
for i in range(3):
    K.key_series(ROOM_LOOK, "location", [K.fr(t) for t, _ in pts], [p[i] for _, p in pts], index=i)

# ----------------------------------------------------------------------------------------- helpers
def lag(x, delay=0.1, tau=0.18):
    """Delayed first-order follower: the head trails the eyes (~100 ms latency, slower motion)."""
    d = int(round(delay * FPS))
    y = np.concatenate([np.full(d, x[0]), x[:len(x) - d]]) if d else x.copy()
    a = 1 - math.exp(-1.0 / (FPS * tau))
    out = np.empty_like(y)
    acc = y[0]
    for i, v in enumerate(y):
        acc += (v - acc) * a
        out[i] = acc
    return out


def eye_pulse(t0, t1, peak=1.0):
    """Gaze switch: eyes jump in ~120 ms (saccade), hold, jump back."""
    return pulse(t0, t1, 0.12, 0.12, peak)


def add_rot_layer(arm, bone, name, use=(False, False, False)):
    """Extra local rotation applied after everything else (Copy Rotation 'AFTER' from an empty)."""
    e = world_empty(f"{arm.name}_{name}", (0, 0, 0))
    e.rotation_mode = "XYZ"
    c = arm.pose.bones[bone].constraints.new("COPY_ROTATION")
    c.name = name
    c.target = e
    c.use_x, c.use_y, c.use_z = use
    c.mix_mode = "AFTER"
    c.target_space = c.owner_space = "LOCAL"
    return e


def saccades(rate_lo, rate_hi, amp_deg, rng, t0=0.0, t1=None, dur=0.04):
    """Fixational saccades: piecewise-constant gaze offsets with ~40 ms jumps (yaw, pitch in radians)."""
    t1 = t1 or TT[-1]
    yaw, pit = np.zeros_like(TT), np.zeros_like(TT)
    t, cy, cp = t0, 0.0, 0.0
    while t < t1:
        ny, npt = rng.normal(0, amp_deg), rng.normal(0, amp_deg * 0.6)
        m = TT >= t
        ramp = np.clip((TT[m] - t) / dur, 0, 1)
        yaw[m] = cy + (ny - cy) * ramp
        pit[m] = cp + (npt - cp) * ramp
        cy, cp = ny, npt
        t += rng.uniform(rate_lo, rate_hi)
    return np.radians(yaw), np.radians(pit)


def smooth_noise(rng, freq, amp):
    """Band-limited noise (postural sway)."""
    n = rng.normal(0, 1, len(TT) + 400)
    k = max(3, int(FPS / freq))
    n = np.convolve(n, np.hanning(k) / np.hanning(k).sum(), "same")[200:200 + len(TT)]
    return n / (np.std(n) + 1e-9) * amp


def stress_peaks(line, t_speech):
    """Times of stressed syllables: prominent peaks of the speech envelope."""
    jaw = np.array(LIPS[line]["jaw"])
    if len(jaw) < 5:
        return []
    sm = np.convolve(jaw, np.ones(3) / 3, "same")
    pk = [i for i in range(2, len(sm) - 2) if sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] > 0.55]
    out, last = [], -99
    for i in pk:
        if i - last > 9:                    # at most ~3 accents per second
            out.append(t_speech + i / FPS - LIP_LEAD)
            last = i
    return out


def accent_curve(times, amp, width=0.22):
    a = np.zeros_like(TT)
    for t in times:
        x = (TT - t) / width
        a += amp * np.exp(-x * x) * (TT > t - 3 * width)
    return a


# ======================================================================================== woman
# Eyes: always on him. They lock onto the lens BEFORE her head starts turning during the scream.
w_hand_eye = eye_pulse(BEATS["look_at_hand"] + 0.25, SPEAK["W03"] - 0.45)
w_cam_eye = (pulse(BEATS["slam"] + 0.25, FREEZE_AT + 2.0, 0.08, 0.1) * (TT < T_EMPTY) + (TT >= T_EMPTY) * 1.0)
w_cam_head = env([(BEATS["slam"] + 0.45, 0.0), (FREEZE_AT - 0.15, 1.0)]) * (TT < T_EMPTY) + (TT >= T_EMPTY) * 1.0
for eye in ("Bip01 LEye", "Bip01 REye"):
    track(WA, eye, M_FACE, "TRACK_X", "eye_man", const=1.0)
    track(WA, eye, W_HAND, "TRACK_X", "eye_hand", w_hand_eye)
    track(WA, eye, CAM_EMPTY, "TRACK_X", "eye_cam", w_cam_eye)
w_head_man = 0.8 * (1 - lag(w_hand_eye, 0.1, 0.2)) * (1 - w_cam_head)
track(WA, "Bip01 Neck", M_FACE, "TRACK_Y", "neck_man", 0.35 * w_head_man)
track(WA, "Bip01 Head", M_FACE, "TRACK_Y", "head_man", w_head_man)
# the turn to the lens is slow and far too smooth -- the only unnatural motion in the film is hers
track(WA, "Bip01 Neck", CAM_EMPTY, "TRACK_Y", "neck_cam", 0.45 * w_cam_head)
track(WA, "Bip01 Head", CAM_EMPTY, "TRACK_Y", "head_cam", w_cam_head)
# head layer: tilt on "Go ahead" (roll = local Y) + tiny speech accents (nod = local Z), almost no sway
W_HEADL = add_rot_layer(WA, "Bip01 Head", "head_layer", (False, True, True))
tilt = env([(BEATS["head_tilt"], 0.0), (BEATS["head_tilt"] + 0.7, 1.0), (SPEAK["W02"] + 1.5, 1.0),
            (SPEAK["W02"] + 2.6, 0.3), (BEATS["smile_back"], 0.3), (BEATS["smile_back"] + 1.5, 1.0),
            (SPEAK["M09"], 1.0), (SPEAK["M09"] + 1.0, 0.4)]) * (TT < T_EMPTY) + (TT >= T_EMPTY) * 0.7
w_acc = sum((stress_peaks(ln, SPEAK[ln]) for ln in ("W01", "W02", "W03", "W04", "W05", "W07")), [])
K.key_series(W_HEADL, "rotation_euler", FRAMES, np.radians(-11) * tilt, index=1)
K.key_series(W_HEADL, "rotation_euler", FRAMES, np.radians(1.4) * accent_curve(w_acc, 1.0)
             + np.radians(0.12) * smooth_noise(np.random.default_rng(21), 0.25, 1.0), index=2)
# eyes: very rare micro-saccades -- she is alive, but barely
W_SACC_L = add_rot_layer(WA, "Bip01 LEye", "sacc", (False, True, True))
W_SACC_R = add_rot_layer(WA, "Bip01 REye", "sacc", (False, True, True))
wy, wp = saccades(3.0, 7.0, 0.35, np.random.default_rng(31))
for e in (W_SACC_L, W_SACC_R):
    K.key_series(e, "rotation_euler", FRAMES, wy, index=1)
    K.key_series(e, "rotation_euler", FRAMES, wp, index=2)
WF.expr("smile_uncanny", accent_curve(w_acc, 0.08) * (TT < BEATS["smile_off"]))        # smile pushes on accents
for ln in ("W01", "W02", "W03", "W04", "W05", "W07"):
    WF.add(AK["browInnerUp"], accent_curve(stress_peaks(ln, SPEAK[ln]), 0.12))

# ======================================================================================== man
cam0 = BEATS["man_looks_at_camera"] + 0.25
m_cam_eye = eye_pulse(cam0, cam0 + 2.3)
m_cam_head = lag(pulse(cam0, cam0 + 2.3, 0.35, 0.5), 0.12, 0.15)
hand0 = SPEAK["W02"] + 1.6
m_hand_eye = np.clip(eye_pulse(hand0, SPEAK["M03"] + 2.4) + eye_pulse(BEATS["look_at_hand"], SPEAK["W03"]) * 0.8, 0, 1)
m_own_eye = eye_pulse(BEATS["ring_off_start"] - 0.2, BEATS["ring_on_table"] + 0.2)
# searching the room (establishing shot): discrete fixations -> eyes jump, head follows a lagged path
m_room = env([(2.5, 0.0), (3.5, 1.0), (T_DIA - 1.0, 1.0), (T_DIA, 0.0)]) * (1 - m_cam_eye)
# Fixation points are generated in HIS field of view (yaw within +-60 deg of where his body faces):
# a target behind the head makes a tracker flip -- real people turn the torso for that instead.
_fy = [-50, 38, -18, 58, 12, -42, 47, -58, 25, -8, 52, -35, 30, -55, 18, 44, -25]
_fd = [3.2, 2.6, 4.0, 2.2, 5.0, 3.0, 2.4, 3.5, 4.4, 1.6, 2.8, 3.8, 2.0, 3.3, 4.6, 2.5, 3.1]
_fz = [1.35, 1.2, 1.5, 1.25, 1.6, 1.1, 1.3, 1.45, 1.2, 0.95, 1.4, 1.25, 1.15, 1.5, 1.3, 1.2, 1.35]
_ft = [2.6, 4.1, 5.3, 7.0, 8.6, 10.9, 12.2, 14.0, 16.4, 18.0, 20.5, 23.1, 29.5, 31.6, 33.8, 36.5, 38.4]
_face = MAN_YAW
fix = []
for t_, dy, d, z in zip(_ft, _fy, _fd, _fz):
    a_ = _face + math.radians(dy)
    fix.append((t_, (MAN_SEAT[0] + d * math.sin(a_), MAN_SEAT[1] - d * math.cos(a_), z)))
for i in range(3):
    K.key_series(ROOM_LOOK, "location", [K.fr(t) for t, _ in fix], [p[i] for _, p in fix], index=i, interp="CONSTANT")
ROOM_HEAD = world_empty("man_room_head", fix[0][1])
for i in range(3):
    raw = np.interp(TT, [t for t, _ in fix], [p[i] for _, p in fix])
    stepped = np.array([fix[max(0, np.searchsorted([t for t, _ in fix], x, "right") - 1)][1][i] for x in TT])
    K.key_series(ROOM_HEAD, "location", FRAMES, lag(stepped, 0.11, 0.22), index=i)
# while he talks he looks away now and then (speakers avert gaze more than listeners)
AWAY = world_empty("man_away", (5.9, 5.6, 0.75))     # the tablecloth / his plate
m_away = np.zeros_like(TT)
for ln, (a, b) in {"M03": (0.35, 1.3), "M07": (0.25, 1.7), "M08": (0.3, 1.4), "M04": (0.9, 1.5)}.items():
    m_away += eye_pulse(SPEAK[ln] + a, SPEAK[ln] + b)
m_away = np.clip(m_away, 0, 1) * (1 - m_hand_eye)
for eye in ("Bip01 LEye", "Bip01 REye"):
    track(MA, eye, W_FACE, "TRACK_X", "eye_woman", const=1.0)
    track(MA, eye, ROOM_LOOK, "TRACK_X", "eye_room", m_room)
    track(MA, eye, AWAY, "TRACK_X", "eye_away", m_away)
    track(MA, eye, W_HAND, "TRACK_X", "eye_hand", m_hand_eye)
    track(MA, eye, M_HAND, "TRACK_X", "eye_own", m_own_eye)
    track(MA, eye, CAM_EMPTY, "TRACK_X", "eye_cam", m_cam_eye)
m_hand_head = lag(np.clip(m_hand_eye, 0, 1), 0.1, 0.25)
m_own_head = lag(m_own_eye, 0.1, 0.25)
m_head_w = np.clip(0.75 * (TT >= T_DIA) * (1 - m_hand_head) * (1 - m_own_head), 0, 1) * (TT < T_EMPTY)
m_head_w[TT >= BEATS["slam"]] = 0.85
track(MA, "Bip01 Neck", ROOM_HEAD, "TRACK_Y", "neck_room", lag(m_room, 0.1, 0.3) * 0.3)
track(MA, "Bip01 Head", ROOM_HEAD, "TRACK_Y", "head_room", lag(m_room, 0.1, 0.3) * 0.7)
track(MA, "Bip01 Head", W_FACE, "TRACK_Y", "head_woman", m_head_w)
track(MA, "Bip01 Head", AWAY, "TRACK_Y", "head_away", lag(m_away, 0.12, 0.3) * 0.3)
track(MA, "Bip01 Head", W_HAND, "TRACK_Y", "head_hand", m_hand_head * 0.7)
track(MA, "Bip01 Head", M_HAND, "TRACK_Y", "head_own", m_own_head * 0.6)
track(MA, "Bip01 Neck", CAM_EMPTY, "TRACK_Y", "neck_cam", m_cam_head * 0.4)
track(MA, "Bip01 Head", CAM_EMPTY, "TRACK_Y", "head_cam", m_cam_head)
# head layer: nods on stressed syllables, a shake on "No.", nervous postural sway
M_HEADL = add_rot_layer(MA, "Bip01 Head", "head_layer", (True, False, True))
m_lines = ("M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09", "M10")
m_acc = sum((stress_peaks(ln, SPEAK[ln]) for ln in m_lines), [])
nod = np.radians(3.2) * accent_curve(m_acc, 1.0, 0.16) + np.radians(0.7) * smooth_noise(np.random.default_rng(41), 0.35, 1.0)
shake = np.zeros_like(TT)
m9 = (TT > SPEAK["M09"] - 0.05) & (TT < SPEAK["M09"] + 0.7)
shake[m9] = np.radians(5.0) * np.sin((TT[m9] - SPEAK["M09"]) * 2 * np.pi * 2.6) * np.exp(-(TT[m9] - SPEAK["M09"]) * 2.2)
K.key_series(M_HEADL, "rotation_euler", FRAMES, shake + np.radians(0.6) * smooth_noise(np.random.default_rng(42), 0.25, 1.0), index=0)
K.key_series(M_HEADL, "rotation_euler", FRAMES, nod, index=2)
# eyes: anxious fixational saccades (frequent, larger)
M_SACC_L = add_rot_layer(MA, "Bip01 LEye", "sacc", (False, True, True))
M_SACC_R = add_rot_layer(MA, "Bip01 REye", "sacc", (False, True, True))
my, mp = saccades(0.35, 1.1, 1.4, np.random.default_rng(51))
for e in (M_SACC_L, M_SACC_R):
    K.key_series(e, "rotation_euler", FRAMES, my, index=1)
    K.key_series(e, "rotation_euler", FRAMES, mp, index=2)
# brows lift on accents; blinks ride on the big gaze shifts (eyes + head turning)
for ln in m_lines:
    MF.add(AK["browInnerUp"], accent_curve(stress_peaks(ln, SPEAK[ln]), 0.22))
    MF.add(AK["browOuterUpL"], accent_curve(stress_peaks(ln, SPEAK[ln]), 0.12))
    MF.add(AK["browOuterUpR"], accent_curve(stress_peaks(ln, SPEAK[ln]), 0.12))
shift_times = [t for t, _ in fix if 2.5 < t < T_DIA] + [cam0, cam0 + 2.3, hand0, BEATS["look_at_hand"],
                                                        BEATS["ring_off_start"] - 0.2, BEATS["ring_on_table"] + 0.2]
grng = random.Random(77)
MF.blinks([t - 0.02 for t in shift_times if grng.random() < 0.65], dur=0.15)
WF.write()
MF.write()


# ======================================================================================== extras: social gaze
def extra_talk(tag):
    """Re-derive the chatter windows used for the extras' faces (same RNG sequence)."""
    r = random.Random(sum(map(ord, tag)))
    blink_times(2.5, T_EMPTY, 2.0, 5.5, r)
    talk = np.zeros_like(TT)
    t = r.uniform(3, 9)
    while t < T_EMPTY:
        d = r.uniform(1.5, 4.5)
        talk[(TT > t) & (TT < t + d)] = 1.0
        t += d + r.uniform(3.0, 10.0)
    return talk


groups = [g for g in [[d["tag"] for d in t["diners"]] for t in OTHER_TABLES] + [["b0a", "b0b"]] if all(x in chars for x in g)]
faces = {}
for g in groups:
    for tag in g:
        faces[tag] = face_empty(f"{tag}_face", chars[tag][0], 10.0)
for g in groups:
    for tag in g:
        arm = chars[tag][0]
        partners = [p for p in g if p != tag]
        rng_g = np.random.default_rng(sum(map(ord, tag)) * 7)
        own_talk = extra_talk(tag)
        listen = np.clip(sum(extra_talk(p) for p in partners), 0, 1)
        # with two partners, attention alternates every few seconds
        sel = np.zeros_like(TT)
        if len(partners) > 1:
            t = 0.0
            cur = 0
            while t < TT[-1]:
                d = rng_g.uniform(2.5, 7.0)
                sel[(TT >= t) & (TT < t + d)] = cur
                cur = 1 - cur
                t += d
        for k, p in enumerate(partners):
            w = (sel == k).astype(float) if len(partners) > 1 else np.ones_like(TT)
            w_eye = np.clip(w * (0.55 + 0.45 * listen - 0.25 * own_talk), 0, 1)
            for eye in ("Bip01 LEye", "Bip01 REye"):
                track(arm, eye, faces[p], "TRACK_X", f"eye_{p}", w_eye if k else np.clip(w_eye + (1 - w) * 0, 0, 1))
            head_w = lag(np.clip(w * (0.18 + 0.32 * listen + 0.1 * smooth_noise(rng_g, 0.15, 1.0)), 0, 0.6), 0.12, 0.4)
            track(arm, "Bip01 Head", faces[p], "TRACK_Y", f"head_{p}", head_w)
        sl = add_rot_layer(arm, "Bip01 LEye", "sacc", (False, True, True))
        sr = add_rot_layer(arm, "Bip01 REye", "sacc", (False, True, True))
        ey, ep = saccades(0.5, 2.0, 1.6, rng_g)
        for e in (sl, sr):
            K.key_series(e, "rotation_euler", FRAMES, ey, index=1)
            K.key_series(e, "rotation_euler", FRAMES, ep, index=2)
print("PERF faces + gaze done", flush=True)
