"""Hand IK (ring removal, table slam), rings, props, lights, blood. Runs in assemble.py's namespace
after assemble_perf.py."""


# ======================================================================================== arm IK rig
def select_only(o):
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def add_arm_ik(arm, side):
    """Helper chain aligned with the limb (Biped bones run along local X, so Blender IK can't use them
    directly). IKX_* carry the original rest orientation and drive the real bones via Copy Transforms."""
    select_only(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    ua, fa, hd = eb[f"Bip01 {side} UpperArm"], eb[f"Bip01 {side} Forearm"], eb[f"Bip01 {side} Hand"]
    cl = eb[f"Bip01 {side} Clavicle"]
    b1 = eb.new(f"IK_UA_{side}")
    b1.head, b1.tail, b1.parent = ua.head.copy(), fa.head.copy(), cl
    b2 = eb.new(f"IK_FA_{side}")
    b2.head, b2.tail, b2.parent = fa.head.copy(), hd.head.copy(), b1
    b2.use_connect = True
    x1 = eb.new(f"IKX_UA_{side}")
    x1.head, x1.tail, x1.roll, x1.parent = ua.head.copy(), ua.tail.copy(), ua.roll, b1
    x2 = eb.new(f"IKX_FA_{side}")
    x2.head, x2.tail, x2.roll, x2.parent = fa.head.copy(), fa.tail.copy(), fa.roll, b2
    for b in (b1, b2, x1, x2):
        b.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")


def setup_ik(arm, side, target, pole, orient, infl):
    pb = arm.pose.bones
    ik = pb[f"IK_FA_{side}"].constraints.new("IK")
    ik.target, ik.pole_target, ik.chain_count = target, pole, 2
    ik.name = "ik"
    cons = []
    for orig, helper in (("UpperArm", "IKX_UA"), ("Forearm", "IKX_FA")):
        c = pb[f"Bip01 {side} {orig}"].constraints.new("COPY_TRANSFORMS")
        c.name = "ik_follow"
        c.target, c.subtarget = arm, f"{helper}_{side}"
        c.target_space = c.owner_space = "WORLD"
        cons.append((f"Bip01 {side} {orig}", c))
    c = pb[f"Bip01 {side} Hand"].constraints.new("COPY_ROTATION")
    c.name = "ik_orient"
    c.target = orient
    c.target_space = c.owner_space = "WORLD"
    cons.append((f"Bip01 {side} Hand", c))
    for bone, c in cons:
        K.key_series(arm, f'pose.bones["{bone}"].constraints["{c.name}"].influence', FRAMES,
                     np.clip(infl, 0, 1), owner=c)
    return ik


def pick_pole_angle(arm, side, ik, pole, t):
    sc.frame_set(int(K.fr(t)))
    best = None
    for a in range(-180, 180, 15):
        ik.pole_angle = math.radians(a)
        bpy.context.view_layer.update()
        elbow = arm.matrix_world @ arm.pose.bones[f"IK_FA_{side}"].head
        d = (elbow - pole.matrix_world.translation).length
        if best is None or d < best[0]:
            best = (d, a)
    ik.pole_angle = math.radians(best[1])
    print(f"IK {side} pole_angle={best[1]} dist={best[0]:.3f}", flush=True)


def frame_axes(yaw):
    f = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    r = Vector((f.y, -f.x, 0.0))
    return f, r, Vector((0, 0, 1))


def orient_matrix(fingers, palm):
    """Hand bone world rotation: Biped hand X runs to the fingers, Y is the palm normal."""
    x = fingers.normalized()
    y = (palm - x * palm.dot(x)).normalized()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed()
    return m


def anim_empty(name, times, locs, rots=None, step=1):
    e = world_empty(name, locs[0])
    e.rotation_mode = "QUATERNION"
    fr_ = [K.fr(t) for t in times]
    L = np.array(locs, dtype=float)
    for i in range(3):
        K.key_series(e, "location", fr_, L[:, i], index=i)
    if rots is not None:
        Q = np.array([list(q) for q in rots], dtype=float)
        for i in range(4):
            K.key_series(e, "rotation_quaternion", fr_, Q[:, i], index=i)
    return e



# ------------------------------------------------------------------------------------------------------
# Hand IK gestures. Principles (to avoid twisted arms / spins):
#  * every gesture starts exactly at the mocap hand position + rotation (no jump when IK blends in);
#  * one target per hand for all gestures (two IK solvers never fight);
#  * minimum-jerk timing (human reaching), arcs instead of straight lines;
#  * rotations interpolated by slerp on the shortest arc, sign-continuous frame to frame;
#  * the IK elbow is aimed (pole) where the mocap elbow already is when the gesture starts.
# ------------------------------------------------------------------------------------------------------
UP = Vector((0, 0, 1))


def min_jerk(x):
    x = min(max(x, 0.0), 1.0)
    return x ** 3 * (10 - 15 * x + 6 * x * x)


def hand_state(arm, side, t):
    sc.frame_set(int(round(K.fr(t))))
    bpy.context.view_layer.update()
    pb = arm.pose.bones
    H = arm.matrix_world @ pb[f"Bip01 {side} Hand"].matrix
    return dict(pos=H.translation.copy(), q=H.to_3x3().normalized().to_quaternion(),
                elbow=(arm.matrix_world @ pb[f"Bip01 {side} Forearm"].head).copy(),
                shoulder=(arm.matrix_world @ pb[f"Bip01 {side} UpperArm"].head).copy())


def gesture_path(keys, arcs=None, tremble=None):
    """keys: [(t, pos, quat)] -> {frame: (pos, quat)} sampled every frame between first and last key."""
    arcs = arcs or {}
    ts = [k[0] for k in keys]
    out = {}
    prev_q = None
    for f in range(int(round(K.fr(ts[0]))), int(round(K.fr(ts[-1]))) + 1):
        t = (f - 1) / FPS
        j = max(0, min(len(keys) - 2, int(np.searchsorted(ts, t, "right")) - 1))
        (t0, p0, q0), (t1, p1, q1) = keys[j], keys[j + 1]
        s = min_jerk((t - t0) / max(t1 - t0, 1e-6))
        p = p0.lerp(p1, s) + UP * arcs.get(j, 0.0) * 4 * s * (1 - s)
        q1a = q1 if q0.dot(q1) >= 0 else -q1
        q = q0.slerp(q1a, s)
        if prev_q is not None and q.dot(prev_q) < 0:
            q = -q
        if tremble is not None:
            p = p + tremble(t)
        out[f] = (p, q)
        prev_q = q
    return out


def bake_target(name, segments, default_state):
    """Merge gesture paths into one per-frame keyed empty (holds the last pose between gestures)."""
    e = world_empty(name, default_state["pos"])
    e.rotation_mode = "QUATERNION"
    merged = {}
    for seg in segments:
        merged.update(seg)
    frames = sorted(merged)
    P = np.array([list(merged[f][0]) for f in frames])
    Q = np.array([list(merged[f][1]) for f in frames])
    for i in range(1, len(Q)):
        if np.dot(Q[i], Q[i - 1]) < 0:
            Q[i] *= -1
    for i in range(3):
        K.key_series(e, "location", frames, P[:, i], index=i)
    for i in range(4):
        K.key_series(e, "rotation_quaternion", frames, Q[:, i], index=i)
    return e


def pole_path(name, keys):
    """Pole target keyed over time: [(t, position)] (smooth)."""
    e = world_empty(name, keys[0][1])
    for i in range(3):
        K.key_series(e, "location", [K.fr(t) for t, _ in keys], [p[i] for _, p in keys], index=i, interp="BEZIER")
    return e


def mocap_pole(st, push=0.35):
    """Point beyond the mocap elbow, away from the shoulder-hand line: IK keeps the same elbow."""
    mid = (st["shoulder"] + st["pos"]) / 2
    d = st["elbow"] - mid
    if d.length < 1e-4:
        d = -UP
    return st["elbow"] + d.normalized() * push


def tremor(seed, amp):
    g = np.random.default_rng(seed)
    ph = g.uniform(0, 6.28, (3, 3))
    return lambda t: Vector([amp * (math.sin(t * 9.1 + ph[k, 0]) + 0.6 * math.sin(t * 13.7 + ph[k, 1])
                                    + 0.4 * math.sin(t * 6.3 + ph[k, 2])) for k in range(3)])


def infl_curve(on_t, off_t, ramp_in=0.2, ramp_out=0.2):
    return env([(on_t, 0.0), (on_t + ramp_in, 1.0), (off_t - ramp_out, 1.0), (off_t, 0.0)], "linear")


# ====================================================================================== the man
f_m, r_m, up = frame_axes(MAN_STAND_YAW)
P0 = Vector((MAN_STAND[0], MAN_STAND[1], 0.0))
T0 = BEATS["ring_off_start"]                       # 100.5 (21:51:42)
T_GRAB, T_PULL0, T_PULL1 = T0 + 1.05, T0 + 1.5, T0 + 2.9
T_DROP, T_LAND = BEATS["ring_on_table"] - 0.2, BEATS["ring_on_table"]
T_SLAM = BEATS["slam"]
toward_man = (Vector((MAN_STAND[0], MAN_STAND[1], 0)) - Vector((C3.x, C3.y, 0))).normalized()

# mocap states needed before any constraint exists
mL0, mL1 = hand_state(MA, "L", T0 - 0.05), hand_state(MA, "L", T_PULL1 + 1.25)
mR0, mR1 = hand_state(MA, "R", T0 + 0.15), hand_state(MA, "R", T_DROP + 1.15)
sL0, sR0 = hand_state(MA, "L", T_SLAM - 0.42), hand_state(MA, "R", T_SLAM - 0.42)
SHOULDER_Z = mL0["shoulder"].z
print("IK shoulder z", round(SHOULDER_Z, 3), flush=True)

# left hand: raised in front of the chest, back of the hand up, fingers pointing to his right
L_POS = P0 + f_m * 0.34 - r_m * 0.03 + up * (SHOULDER_Z - 0.27)
L_ROT = orient_matrix((f_m * 0.55 + r_m * 0.83 + up * 0.08).normalized(), -up * 0.75 - f_m * 0.65).to_quaternion()
trL = tremor(11, 0.0022)
gL_ring = gesture_path([(T0 - 0.05, mL0["pos"], mL0["q"]), (T0 + 0.85, L_POS, L_ROT),
                        (T_PULL1 + 0.35, L_POS, L_ROT), (T_PULL1 + 1.25, mL1["pos"], mL1["q"])],
                       arcs={0: 0.05}, tremble=lambda t: trL(t) * (T0 + 0.6 < t < T_PULL1 + 0.5))

# slam: from wherever the mocap hands are, up a little, then down flat on the table
# palms land on the two clear spots of his edge of the table (>= 12 cm from glasses, plates, napkin)
SL_L = Vector((C3.x + 0.11, C3.y + 0.35, TOP + 0.035))
SL_R = Vector((C3.x - 0.08, C3.y + 0.36, TOP + 0.035))
slam_qL = orient_matrix((f_m + r_m * 0.25).normalized(), -up).to_quaternion()
slam_qR = orient_matrix((f_m - r_m * 0.25).normalized(), -up).to_quaternion()
END_T = FREEZE_AT + 0.5
gL_slam = gesture_path([(T_SLAM - 0.42, sL0["pos"], sL0["q"]), (T_SLAM - 0.13, SL_L + up * 0.10, slam_qL),
                        (T_SLAM, SL_L, slam_qL), (END_T, SL_L, slam_qL)])
gR_slam = gesture_path([(T_SLAM - 0.42, sR0["pos"], sR0["q"]), (T_SLAM - 0.13, SL_R + up * 0.10, slam_qR),
                        (T_SLAM, SL_R, slam_qR), (END_T, SL_R, slam_qR)])

L_TGT = bake_target("man_L_tgt", [gL_ring, gL_slam], mL0)
L_POLE = pole_path("man_L_pole", [(T0 - 0.05, mocap_pole(mL0)), (T0 + 0.9, P0 - r_m * 0.45 - f_m * 0.15 + up * (SHOULDER_Z - 0.55)),
                                  (T_PULL1 + 0.4, P0 - r_m * 0.45 - f_m * 0.15 + up * (SHOULDER_Z - 0.55)),
                                  (T_PULL1 + 1.25, mocap_pole(mL1)), (T_SLAM - 0.42, mocap_pole(sL0)),
                                  (T_SLAM, P0 - r_m * 0.45 + f_m * 0.05 + up * (SHOULDER_Z - 0.35))])
inflL = np.maximum(infl_curve(T0 - 0.05, T_PULL1 + 1.25, 0.2, 0.2), infl_curve(T_SLAM - 0.42, END_T + 1, 0.12, 0.01))
add_arm_ik(MA, "L")
ikL = setup_ik(MA, "L", L_TGT, L_POLE, L_TGT, inflL)


def pick_pole_angle(arm, side, ik, t, want_elbow):
    """Choose the pole angle whose IK elbow lands closest to the mocap elbow at gesture start."""
    sc.frame_set(int(round(K.fr(t))))
    best = None
    for a_ in range(-180, 180, 5):
        ik.pole_angle = math.radians(a_)
        bpy.context.view_layer.update()
        elbow = arm.matrix_world @ arm.pose.bones[f"IK_FA_{side}"].head
        d = (elbow - want_elbow).length
        if best is None or d < best[0]:
            best = (d, a_)
    ik.pole_angle = math.radians(best[1])
    print(f"IK {arm.name} {side} pole_angle={best[1]} elbow error={best[0] * 100:.1f} cm", flush=True)


pick_pole_angle(MA, "L", ikL, T0 - 0.05, mL0["elbow"])

# ring on the raised left hand, measured on the solved pose
sc.frame_set(int(round(K.fr(T_GRAB))))
bpy.context.view_layer.update()
F3M = MA.matrix_world @ MA.pose.bones["Bip01 L Finger3"].matrix
FING_DIR = Vector(F3M.col[0][:3]).normalized()
RING0 = F3M.translation + FING_DIR * 0.013
print("IK ring0", tuple(round(v, 3) for v in RING0), "finger dir", tuple(round(v, 2) for v in FING_DIR), flush=True)

# right hand: approach, pinch, twist the ring off along the finger, carry it over the table, let go
# Thumb-up pinch (palm toward his chest): forearm close to neutral rotation. Palm-down with the
# fingers pointing left needs >100 deg of pronation -> a wrung, candy-wrapper wrist (caught by qa_motion).
R_FING = (-FING_DIR * 0.85 + f_m * 0.25 - up * 0.2).normalized()
R_ROT = orient_matrix(R_FING, -f_m * 0.8 - up * 0.3).to_quaternion()
CARRY_ROT = orient_matrix((f_m * 0.8 - r_m * 0.35).normalized(), -up * 0.6 - r_m * 0.5).to_quaternion()
PINCH = 0.088                                      # wrist -> thumb/index pinch point
DROP_PT = Vector((C3.x + 0.03, C3.y + 0.32, TOP + 0.20))      # free cloth: >=12 cm from glass, cutlery, slam spots
ring_track = []                                    # (t, world position) of the ring while in his hand
keys_R = [(T0 + 0.15, mR0["pos"], mR0["q"]),
          (T_GRAB - 0.3, RING0 - R_FING * (PINCH + 0.05) + up * 0.02, R_ROT),
          (T_GRAB, RING0 - R_FING * PINCH, R_ROT)]
gR = gesture_path(keys_R, arcs={0: 0.06})
for f in range(int(round(K.fr(T_GRAB))) + 1, int(round(K.fr(T_DROP + 1.15))) + 1):
    t = (f - 1) / FPS
    if t <= T_PULL1:
        s = min_jerk((t - T_PULL0) / (T_PULL1 - T_PULL0)) * 0.078
        wig = 0.004 * math.sin((t - T_PULL0) * 22.0) * (T_PULL0 < t < T_PULL1)
        ring = RING0 + FING_DIR * s + trL(t) + r_m * wig
        q = R_ROT
    elif t <= T_DROP:
        x = min_jerk((t - T_PULL1) / (T_DROP - T_PULL1))
        ring = (RING0 + FING_DIR * 0.078).lerp(DROP_PT, x) + UP * 0.06 * 4 * x * (1 - x)
        q = R_ROT.slerp(CARRY_ROT if R_ROT.dot(CARRY_ROT) >= 0 else -CARRY_ROT, x)
    else:                                          # empty hand drifts back to the mocap pose
        x = min_jerk((t - T_DROP - 0.25) / 0.9)
        ring = None
        q0 = CARRY_ROT
        p_hold = DROP_PT - (CARRY_ROT.to_matrix() @ Vector((1, 0, 0))) * PINCH
        gR[f] = (p_hold.lerp(mR1["pos"], x), q0.slerp(mR1["q"] if q0.dot(mR1["q"]) >= 0 else -mR1["q"], x))
        continue
    ring_track.append((t, ring))
    fingers = q.to_matrix() @ Vector((1, 0, 0))
    gR[f] = (ring - fingers * PINCH, q)
R_TGT = bake_target("man_R_tgt", [gR, gR_slam], mR0)
R_POLE = pole_path("man_R_pole", [(T0 + 0.15, mocap_pole(mR0)), (T_GRAB, P0 + r_m * 0.5 - f_m * 0.15 + up * (SHOULDER_Z - 0.6)),
                                  (T_DROP, P0 + r_m * 0.5 + up * (SHOULDER_Z - 0.55)), (T_DROP + 1.15, mocap_pole(mR1)),
                                  (T_SLAM - 0.42, mocap_pole(sR0)), (T_SLAM, P0 + r_m * 0.45 + f_m * 0.05 + up * (SHOULDER_Z - 0.35))])
inflR = np.maximum(infl_curve(T0 + 0.15, T_DROP + 1.15, 0.2, 0.2), infl_curve(T_SLAM - 0.42, END_T + 1, 0.12, 0.01))
add_arm_ik(MA, "R")
ikR = setup_ik(MA, "R", R_TGT, R_POLE, R_TGT, inflR)
pick_pole_angle(MA, "R", ikR, T0 + 0.15, mR0["elbow"])

# lean over the table for the scream (spine up-axis = local X)
LEAN = world_empty("man_lean", tuple(P0 + f_m * 0.75 + up * 1.75))
lean = env([(T_SLAM - 0.35, 0.0), (T_SLAM, 1.0), (FREEZE_AT + 1, 1.0)]) * 0.55
track(MA, "Bip01 Spine1", LEAN, "TRACK_X", "lean1", lean * 0.8)
track(MA, "Bip01 Spine2", LEAN, "TRACK_X", "lean2", lean)

# right-hand pinch: fingers flex toward the palm (+Z in Biped finger space, verified on the mocap)
curl = {"Bip01 R Finger1": 30, "Bip01 R Finger11": 40, "Bip01 R Finger12": 25, "Bip01 R Finger0": 8,
        "Bip01 R Finger01": 15, "Bip01 R Finger02": 15, "Bip01 R Finger2": 45, "Bip01 R Finger21": 60,
        "Bip01 R Finger22": 40, "Bip01 R Finger3": 50, "Bip01 R Finger31": 65, "Bip01 R Finger32": 40,
        "Bip01 R Finger4": 55, "Bip01 R Finger41": 65, "Bip01 R Finger42": 40}
pinch_act = bpy.data.actions.new("man_pinch")
saved_act = MA.animation_data.action
MA.animation_data.action = pinch_act
p_start = T_GRAB - 0.35
key_t = [(0.0, 0.0), (0.35, 1.0), (T_DROP - p_start, 1.0), (T_DROP - p_start + 0.15, 0.0)]
for bone, deg in curl.items():
    pb = MA.pose.bones[bone]
    pb.rotation_mode = "QUATERNION"
    for dt, amt in key_t:
        pb.rotation_quaternion = Quaternion((0, 0, 1), math.radians(deg * amt))
        pb.keyframe_insert("rotation_quaternion", frame=1 + dt * FPS)
    pb.rotation_quaternion = (1, 0, 0, 0)
MA.animation_data.action = saved_act
tr_p = MA.animation_data.nla_tracks.new()
tr_p.name = "pinch"
st = tr_p.strips.new("pinch", int(round(K.fr(p_start))), pinch_act)
if hasattr(st, "action_slot") and st.action_slot is None and len(pinch_act.slots):
    st.action_slot = pinch_act.slots[0]
st.blend_type = "COMBINE"
st.extrapolation = "NOTHING"
st.use_auto_blend = False

# ====================================================================================== the woman
# "She looks at her own hand... genuinely confused": the left hand rises above the table, close to
# her body, back of the hand toward her, she turns it slowly, then lets it sink back.
f_w, r_w, _ = frame_axes(WOMAN_YAW)
WP = Vector((WOMAN_SEAT[0], WOMAN_SEAT[1], 0.0))
tA = BEATS["look_at_hand"] - 0.1
tA2, tB, tC = tA + 0.4, tA + 1.1, tA + 2.7
tD = SPEAK["W03"] + 0.3
tD2, tE = tD + 0.55, tD + 1.3
wA, wE = hand_state(WA, "L", tA), hand_state(WA, "L", tE)
W_SHOULDER = wA["shoulder"]
P_UP = Vector((WP.x, WP.y, 0)) + f_w * 0.27 - r_w * 0.03 + UP * max(TOP + 0.22, W_SHOULDER.z - 0.16)
Q_UP = orient_matrix((f_w * 0.8 + r_w * 0.45 + UP * 0.25).normalized(), -UP * 0.85 - f_w * 0.2).to_quaternion()
fing_axis = Q_UP.to_matrix() @ Vector((1, 0, 0))
Q_TURN = Quaternion(fing_axis, math.radians(-28)) @ Q_UP          # turns the hand to catch the ring
# up first (clear of the table edge), then forward; on the way back: toward the body first, then down
P_LIFT = wA["pos"] + UP * 0.11
P_BACK = Vector((WP.x, WP.y, 0)) + f_w * 0.14 - r_w * 0.03 + UP * (TOP + 0.12)
q_back = Q_TURN.slerp(wE["q"] if Q_TURN.dot(wE["q"]) >= 0 else -wE["q"], 0.5)
gW = gesture_path([(tA, wA["pos"], wA["q"]), (tA2, P_LIFT, wA["q"]), (tB, P_UP, Q_UP),
                   (tC, P_UP + f_w * 0.02 + UP * 0.015, Q_TURN), (tD, P_UP + UP * 0.01, Q_TURN),
                   (tD2, P_BACK, q_back), (tE, wE["pos"], wE["q"])],
                  tremble=lambda t: tremor(23, 0.0006)(t))
WL_TGT = bake_target("woman_L_tgt", [gW], wA)
WL_POLE = pole_path("woman_L_pole", [(tA, mocap_pole(wA)), (tB, W_SHOULDER - r_w * 0.28 - f_w * 0.05 - UP * 0.3),
                                     (tD, W_SHOULDER - r_w * 0.28 - f_w * 0.05 - UP * 0.3), (tE, mocap_pole(wE))])
inflW = infl_curve(tA, tE, 0.2, 0.2)
add_arm_ik(WA, "L")
ikW = setup_ik(WA, "L", WL_TGT, WL_POLE, WL_TGT, inflW)
pick_pole_angle(WA, "L", ikW, tA, wA["elbow"])
# her head follows the hand (eyes already do, ~100 ms earlier)
track(WA, "Bip01 Head", W_HAND, "TRACK_Y", "head_hand", lag(w_hand_eye, 0.1, 0.25) * 0.7)
print("PERF ik done", flush=True)

# ======================================================================================== rings
M_GOLD = S.simple("gold", (1.0, 0.72, 0.32), rough=0.18, metal=1.0)
M_DIAMOND = S.simple("diamond", (1.0, 1.0, 1.0), rough=0.0, transmission=1.0, ior=2.4)


def ring_mesh(name, major, minor, with_stone=False):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=48, minor_segments=12)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(M_GOLD)
    for p in o.data.polygons:
        p.use_smooth = True
    if with_stone:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=minor * 2.2, subdivisions=2, location=(major + minor * 1.6, 0, 0))
        s = bpy.context.active_object
        s.data.materials.append(M_DIAMOND)
        s.parent = o
        S.link(s, CH)
    S.link(o, CH)
    return o


def attach_to_finger(obj, arm, bone, t, along=0.013):
    """Parent obj to `bone` so its hole wraps the finger (torus axis = finger direction)."""
    sc.frame_set(int(K.fr(t)))
    bpy.context.view_layer.update()
    M = arm.matrix_world @ arm.pose.bones[bone].matrix
    d = Vector(M.col[0][:3]).normalized()
    pos = M.translation + d * along
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = Matrix.Translation(pos) @ rot


W_RING = ring_mesh("woman_ring", 0.0082, 0.0011, True)
attach_to_finger(W_RING, WA, "Bip01 L Finger3", 10.0)
K.visibility(W_RING, [(0.0, T_EMPTY), (T_APPEAR, FILM_END + 1)], NF)
M_RING_A = ring_mesh("man_ring_finger", 0.0096, 0.0014)
attach_to_finger(M_RING_A, MA, "Bip01 L Finger3", T_GRAB)
M_RING_B = ring_mesh("man_ring_world", 0.0096, 0.0014)
K.visibility(M_RING_A, [(0.0, T_PULL0)], NF)
K.visibility(M_RING_B, [(T_PULL0, FILM_END + 1)], NF)
# world ring: follows the pinch, then drops, bounces and spins down on the tablecloth (Euler's disk)
times, locs, quats = [], [], []
axis0 = FING_DIR.to_track_quat("Z", "Y")
for t, p in ring_track:                 # in his fingers: follows the pinch point
    if t < T_PULL0 - 0.05 or t > T_DROP:
        continue
    times.append(t)
    locs.append(tuple(p))
    quats.append(axis0 @ Quaternion((0, 0, 1), max(0.0, t - T_PULL0) * 2.0))
LAND = Vector((DROP_PT.x, DROP_PT.y, TOP + 0.009 + 0.0016))
q_flat = Quaternion((1, 0, 0, 0))
t = T_DROP
h0 = DROP_PT.z - LAND.z
while t < T_DROP + 3.0:
    t += 1 / FPS
    u = t - T_DROP
    tf = math.sqrt(2 * h0 / 9.81)
    if u < tf:
        p = DROP_PT.lerp(LAND, (u / tf) ** 2)
        q = axis0.slerp(q_flat, u / tf)
    else:
        v = u - tf
        bounce = 0.018 * abs(math.sin(v * 18)) * math.exp(-v * 9)
        tilt = 0.5 * math.exp(-v * 2.2) * (1 - math.exp(-v * 30))
        prec = 18 * v * (1 + v)             # precession speeds up as it settles
        p = LAND + Vector((0.025 * (1 - math.exp(-v * 3)), 0.012 * (1 - math.exp(-v * 3)), bounce))
        q = Quaternion((math.cos(prec), math.sin(prec), 0), tilt) @ Quaternion((0, 0, 1), prec * 0.3)
    times.append(t)
    locs.append(tuple(p))
    quats.append(q)
RING_REST = Vector(locs[-1])
M_RING_B.rotation_mode = "QUATERNION"
Lr = np.array(locs)
Qr = np.array([list(q) for q in quats])
for i in range(3):
    K.key_series(M_RING_B, "location", [K.fr(x) for x in times], Lr[:, i], index=i)
for i in range(4):
    K.key_series(M_RING_B, "rotation_quaternion", [K.fr(x) for x in times], Qr[:, i], index=i)
T_RING_STILL = times[-1]
print("PERF rings done; ring rests at", tuple(round(v, 3) for v in RING_REST), flush=True)

# ======================================================================================== props & lights
def key_const(obj, path, pairs, index=-1):
    """pairs: [(t, value), ...] stepped."""
    K.key_series(obj, path, [K.fr(t) for t, _ in pairs], [v for _, v in pairs], index=index, interp="CONSTANT")


# his chair is pushed back once he is on his feet; her chair is turned to the lens in the empty restaurant
ch_m = bpy.data.objects["chair_man"]
ch_w = bpy.data.objects["chair_woman"]
(pos_p, yaw_p) = MAN_CHAIR_PUSHED
for i in range(3):
    key_const(ch_m, "location", [(0, ch_m.location[i]), (T_STAND, pos_p[i])], i)
key_const(ch_m, "rotation_euler", [(0, ch_m.rotation_euler[2]), (T_STAND, yaw_p)], 2)
key_const(ch_w, "rotation_euler", [(0, ch_w.rotation_euler[2]), (T_EMPTY, WOMAN_FINAL_YAW)], 2)
# final shot: "sit chair" mocap leans back further -> the turned chair sits 6 cm further back too
_ff = Vector((math.sin(WOMAN_FINAL_YAW), -math.cos(WOMAN_FINAL_YAW), 0))
_fin = Vector((WOMAN_FINAL_SEAT[0], WOMAN_FINAL_SEAT[1], 0)) - _ff * (0.06 + CHAIR_BACK.get("woman_final", 0.0))
for i in range(2):
    key_const(ch_w, "location", [(0, ch_w.location[i]), (T_EMPTY, _fin[i])], i)

# candles flicker; the couple's candle is out in the empty restaurant
for o in [x for x in bpy.data.objects if x.type == "LIGHT" and x.get("vama_candle")]:
    g = np.random.default_rng(len(o.name))
    n = np.cumsum(g.normal(0, 1, len(TT)))
    n = (n - np.convolve(n, np.ones(15) / 15, "same"))
    e = o.data.energy * np.clip(1 + 0.12 * n / (np.std(n) + 1e-6), 0.6, 1.4)
    e[TT >= T_EMPTY] = 0.0 if o.name.startswith("couple") else e[TT >= T_EMPTY]
    if o.name.startswith("couple"):
        e[(TT > T_SLAM) & (TT < T_SLAM + 0.5)] *= 0.55     # the slam shakes the flame
    K.key_series(o.data, "energy", FRAMES, e)
fl = bpy.data.objects.get("couple_flame")
if fl:
    K.visibility(fl, [(0.0, T_EMPTY)], NF)
# glasses, plates and the candle jump when he slams the table
for o in [x for x in bpy.data.objects if x.name.startswith(("couple_d0", "couple_d1", "couple_votive", "couple_wax",
                                                            "couple_flame", "couple_bottle"))]:
    z0 = o.location.z
    hop = np.zeros_like(TT)
    m = (TT >= T_SLAM) & (TT < T_SLAM + 0.25)
    hop[m] = 0.004 * np.sin(np.pi * (TT[m] - T_SLAM) / 0.12) * np.exp(-(TT[m] - T_SLAM) * 12)
    hop = np.abs(hop)
    sel = (TT > T_SLAM - 0.2) & (TT < T_SLAM + 0.4)
    K.key_series(o, "location", np.concatenate([[1], FRAMES[sel], [FRAMES[-1]]]),
                 np.concatenate([[z0], z0 + hop[sel], [z0]]), index=2)

# the pendant above their table stutters in the empty restaurant
pend = next(o for o in bpy.data.objects if o.get("vama_pendant") == 0)
e = np.full_like(TT, pend.data.energy)
g = np.random.default_rng(3)
m = TT >= T_EMPTY
drop = (g.random(len(TT)) < 0.035) & m
for i in np.where(drop)[0]:
    e[i:i + g.integers(2, 6)] *= g.uniform(0.05, 0.5)
e[(TT > SEG["empty"][1] + 16.0) & (TT < SEG["empty"][1] + 17.6)] *= 0.15   # brown-out as she appears
K.key_series(pend.data, "energy", FRAMES, e)

# passing cars: headlights sweep through the windows
cars = [x for x in bpy.data.objects if x.get("vama_carlight") is not None]
for o in cars:
    k = o["vama_carlight"]
    pairs_y, pairs_e = [(0, -40.0)], [(0, 0.0)]
    for tc in (BEATS["car_pass_1"], BEATS["car_pass_2"]):
        pairs_y += [(tc - 0.01, -28.0), (tc + 5.0, 42.0), (tc + 5.01, -40.0)]
        pairs_e += [(tc - 0.01, 0.0), (tc, 60000.0), (tc + 5.0, 60000.0), (tc + 5.01, 0.0)]
    fy = [K.fr(t) for t, _ in pairs_y]
    K.key_series(o, "location", fy, [v + (0.0 if k == 0 else 1.3) for _, v in pairs_y], index=1, interp="LINEAR")
    K.key_series(o.data, "energy", [K.fr(t) for t, _ in pairs_e], [v for _, v in pairs_e], interp="LINEAR")
    o.location.x = ROOM[0] + 5.5
    o.location.z = 0.75
    d = Vector((-0.55, 1.0, -0.03)).normalized()
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

# kitchen swing door (hinge at its outer edge) for the waiter
door = bpy.data.objects["kdoor_1"]
hinge = world_empty("kdoor_hinge", (KITCHEN_DOOR[1], ROOM[1] + 0.045, 0.0))
door.parent = hinge
door.matrix_parent_inverse = hinge.matrix_world.inverted()
pairs = [(0.0, 0.0)]
for w in WAITER["walks"]:
    td, sgn = w["door_t"], w["door_dir"]
    pairs += [(td - 0.45, 0.0), (td - 0.05, sgn * 1.25), (td + 0.55, sgn * 1.25)]
    for k in range(1, 7):     # damped swing back and forth
        pairs.append((td + 0.55 + k * 0.45, -sgn * 1.25 * (0.55 ** k) * (-1) ** (k + 1)))
    pairs.append((td + 4.0, 0.0))
pairs.sort()
K.key_series(hinge, "rotation_euler", [K.fr(t) for t, _ in pairs], [v for _, v in pairs], index=2, interp="BEZIER")
for w in WAITER["walks"]:
    print("DOOR at", round(w["door_t"], 2), flush=True)

# wall clock: the second hand follows the CCTV clock; it stops in the empty restaurant
sec = next((o for o in bpy.data.objects if o.get("vama_second_hand")), None)
if sec:
    base = sec.rotation_euler.copy()
    vals = []
    for t in TT:
        c = clock_at(t)
        vals.append(int(c[-2:]) if c and t < T_EMPTY else 47)
    sec.rotation_mode = "XYZ"
    ang = [base.y - math.radians(6 * v) for v in vals]
    K.key_series(sec, "rotation_euler", FRAMES, ang, index=1, interp="CONSTANT")

# ======================================================================================== blood
M_BLOOD = S.simple("blood", (0.16, 0.0, 0.004), rough=0.08, coat=1.0)
M_BLOOD_DRY = S.simple("blood_smear", (0.1, 0.005, 0.004), rough=0.35)
BLOOD = S.coll("blood")


def blob(name, center, radius, seed, irregular=0.35, points=64, mat=M_BLOOD, height=0.002, squash=(1.0, 1.0)):
    g = np.random.default_rng(seed)
    ang = np.linspace(0, 2 * np.pi, points, endpoint=False)
    rr = np.ones(points)
    for k, a in ((2, 0.5), (3, 0.35), (5, 0.25), (9, 0.15), (17, 0.08)):
        rr += irregular * a * np.sin(k * ang + g.uniform(0, 6.28))
    rr = np.clip(rr, 0.35, None) * radius
    me = bpy.data.meshes.new(name)
    vs = [(center[0], center[1], height)] + [(center[0] + rr[i] * math.cos(ang[i]) * squash[0],
                                              center[1] + rr[i] * math.sin(ang[i]) * squash[1], height)
                                             for i in range(points)]
    fs = [(0, 1 + i, 1 + (i + 1) % points) for i in range(points)]
    me.from_pydata(vs, [], fs)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    BLOOD.objects.link(ob)
    me.materials.append(mat)
    m = ob.modifiers.new("sub", "SUBSURF")
    m.levels = m.render_levels = 2
    return ob


g = np.random.default_rng(99)
pool_c = (MAN_STAND[0] - 0.12, MAN_STAND[1] + 0.12)
blob("blood_pool", pool_c, 0.42, 1, 0.45, squash=(1.25, 0.85))
blob("blood_pool2", (pool_c[0] + 0.35, pool_c[1] - 0.55), 0.2, 2, 0.5)   # runs under the table
for i in range(40):
    a, d = g.uniform(0, 6.28), g.uniform(0.45, 1.6)
    blob(f"blood_drop_{i}", (pool_c[0] + d * math.cos(a), pool_c[1] + d * math.sin(a)), g.uniform(0.008, 0.035), 10 + i, 0.6)
# drag smear toward the kitchen door
for i in range(14):
    u = i / 13
    p = (pool_c[0] * (1 - u) + 4.9 * u, pool_c[1] * (1 - u) + 8.9 * u)
    blob(f"blood_smear_{i}", p, 0.16 * (1 - 0.6 * u), 60 + i, 0.25, mat=M_BLOOD_DRY, squash=(0.6, 1.4))
for o in BLOOD.objects:
    K.visibility(o, [(T_EMPTY, FILM_END + 1)], NF)
print("PERF props done", flush=True)
