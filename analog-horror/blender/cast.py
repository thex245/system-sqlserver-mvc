"""Cast, placements and body-clip plans (film seconds). Imported by bake_cast.py and assemble.py."""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from layout import *          # noqa: F401,F403
from timeline import BEATS, SEG, FREEZE_AT

CLIP_LEN = {
    "m_sit_table_idle_nervous_01": 1020, "m_sit_table_idle_look_around": 261, "m_sit_table_idle_waiting_01": 979,
    "m_sit_table_breathe_01": 382, "m_sit_table_gestic_shrug_02": 120, "m_gestic_talk_angry_01": 1179,
    "m_idle_nervous_02": 1533, "m_idle_angry_02": 506, "m_idle_neutral_03": 1001, "m_idle_neutral_04": 1111,
    "m_sit_table_idle_neutral_01": 1372, "m_sit_table_idle_neutral_02": 1094, "m_sit_table_idle_relaxed_01": 1331,
    "m_sit_table_gestic_thoughtful": 501, "m_sit_table_idle_touch_face": 226, "m_sit_table_idle_scratch_head": 285,
    "f_sit_table_breathe_01": 577, "f_sit_chair_breathe_01": 577, "f_sit_table_idle_neutral_01": 788,
    "f_sit_table_idle_neutral_02": 669, "f_sit_table_idle_relaxed_01": 831, "f_sit_table_idle_waiting_01": 767,
    "f_sit_table_gestic_thoughtful": 455, "f_sit_table_idle_touch_hair": 185, "f_sit_table_gestic_shrug_02": 124,
    "f_sit_table_idle_touch_face": 131, "f_work_table": 850, "m_walk_neutral": 33,
    "f_sit_chair_idle_finger nail": 206,
}
FPS = 30


def strip(clip, t0, t1, offset=1, blend=0.5, cycles=None):
    """A clip played on the film timeline from t0 to t1 starting at clip frame `offset`."""
    return dict(clip=clip, t0=t0, t1=t1, offset=offset, blend=blend, cycles=cycles)


def fill(pool, t0, t1, rng, first_offset=True):
    """Chain random clips from pool with 0.8 s crossfades until t1."""
    out, t = [], t0
    last = None
    while t < t1:
        clip = rng.choice([c for c in pool if c != last])
        n = CLIP_LEN[clip]
        off = rng.randint(1, max(1, n // 2)) if (first_offset and not out) else 1
        dur = min((n - off) / FPS, t1 - t + 0.8)
        if dur < 2.5 and out:
            out[-1]["t1"] = t1
            break
        out.append(strip(clip, t, t + dur, off, 0.8))
        last = clip
        t = t + dur - 0.8
    return out


M_POOL = ["m_sit_table_idle_neutral_01", "m_sit_table_idle_neutral_02", "m_sit_table_idle_relaxed_01",
          "m_sit_table_idle_waiting_01", "m_sit_table_gestic_thoughtful", "m_sit_table_idle_touch_face",
          "m_sit_table_breathe_01", "m_sit_table_idle_scratch_head"]
F_POOL = ["f_sit_table_idle_neutral_01", "f_sit_table_idle_neutral_02", "f_sit_table_idle_relaxed_01",
          "f_sit_table_idle_waiting_01", "f_sit_table_idle_touch_hair",
          "f_sit_table_breathe_01", "f_sit_table_idle_touch_face"]

T_START, T_END = 2.5, FREEZE_AT + 0.6
E0 = SEG["establish"][1]

# Leads -----------------------------------------------------------------------------------------
MAN = dict(tag="man", avatar="Business_Male_01", hero=True, pelvis=MAN_SEAT, yaw=MAN_YAW, sex="m", strips=[
    strip("m_sit_table_idle_nervous_01", T_START, 22.0, 1, 0.0),
    strip("m_sit_table_idle_look_around", 21.5, 30.2, 1, 0.5),
    strip("m_sit_table_idle_nervous_01", 29.7, 41.5, 571, 0.5),
    strip("m_sit_table_idle_waiting_01", 41.0, 73.6, 1, 0.5),
    strip("m_sit_table_breathe_01", 73.1, 79.5, 1, 0.5),
    # standing (after the interference at 79.5 the picture returns with him on his feet)
    strip("m_gestic_talk_angry_01", 79.5, 99.5, 1, 0.0),
    # ring + scream: a standing clip with almost no root drift (+-3 cm) so world-space hand IK stays put
    strip("m_idle_angry_02", 99.5, T_END, 1, 0.0),
])
WOMAN = dict(tag="woman", avatar="Female_Adult_11", hero=True, pelvis=WOMAN_SEAT, yaw=WOMAN_YAW, sex="f", strips=[
    strip("f_sit_table_breathe_01", T_START, 22.0, 1, 0.0),
    strip("f_sit_table_breathe_01", 21.2, 40.4, 1, 0.8),
    strip("f_sit_table_breathe_01", 39.6, 58.8, 1, 0.8),
    strip("f_sit_table_breathe_01", 58.0, 77.2, 1, 0.8),
    strip("f_sit_table_breathe_01", 76.4, 95.6, 1, 0.8),
    strip("f_sit_table_breathe_01", 94.8, T_END, 1, 0.8),
    # "she looks at her own hand... genuinely confused" is an IK gesture (assemble_props.py): the
    # available mocap looks at a hand resting in the lap, which is hidden under the table edge.
    # final apparition: chair turned to the lens, hands in her lap
    strip("f_sit_chair_breathe_01", SEG["empty"][1] + 15.5, SEG["end"][1] + 0.5, 1, 0.0),
])

# Extras --------------------------------------------------------------------------------------
_rng = random.Random(1997)
EXTRAS = []
_assign = {"t1a": ("Male_Adult_02", "m"), "t1b": ("Female_Adult_05", "f"), "t2a": ("Business_Male_03", "m"),
           "t2b": ("Female_Adult_08", "f"), "t3a": ("Female_Adult_13", "f"), "t3b": ("Male_Adult_09", "m"),
           "t3c": ("Female_Adult_14", "f"), "t4a": ("Male_Adult_13", "m"), "t4b": ("Female_Adult_17", "f"),
           "b0a": ("Male_Adult_16", "m"), "b0b": ("Female_Adult_01", "f"), "b1a": ("Male_Adult_03", "m")}
# clips whose leg crossing lifts a knee into this diner's (rectangular, aproned) table -- found by qa_contacts
_EXCLUDE = {"t2b": {"f_sit_table_idle_neutral_02", "f_sit_table_gestic_thoughtful", "f_sit_table_idle_relaxed_01", "f_sit_table_idle_neutral_01", "f_sit_table_idle_waiting_01"}}
for t in OTHER_TABLES:
    for d in t["diners"]:
        av, sex = _assign[d["tag"]]
        pool = [c for c in (M_POOL if sex == "m" else F_POOL) if c not in _EXCLUDE.get(d["tag"], ())]
        EXTRAS.append(dict(tag=d["tag"], avatar=av, hero=False, pelvis=d["pelvis"], yaw=d["yaw"], sex=sex,
                           strips=fill(pool, T_START, T_END, random.Random(int.from_bytes(d["tag"].encode(), "big") * 7919))))
for d in BOOTH_DINERS:
    av, sex = _assign[d["tag"]]
    EXTRAS.append(dict(tag=d["tag"], avatar=av, hero=False, pelvis=d["pelvis"], yaw=d["yaw"], sex=sex,
                       strips=fill(M_POOL if sex == "m" else F_POOL, T_START, T_END, random.Random(int.from_bytes(d["tag"].encode(), "big") * 7919))))
EXTRAS.append(dict(tag="bar", avatar="Male_Adult_20", hero=False, pelvis=(2.55, BAR_Y - 0.55 - 0.42), yaw=math.pi,
                   sex="m", strips=[strip("m_idle_neutral_04", T_START, 39.5, 1, 0.0),
                                    strip("m_idle_neutral_03", 38.7, 72.0, 1, 0.8),
                                    strip("m_idle_neutral_04", 71.2, T_END, 1, 0.8)]))
EXTRAS.append(dict(tag="chef", avatar="Chef_Female_01", hero=False, pelvis=(5.65, ROOM[1] + 1.55), yaw=0.0, sex="f",
                   strips=[strip("f_work_table", T_START, 30.8, 1, 0.0), strip("f_work_table", 30.0, 58.3, 1, 0.8),
                           strip("f_work_table", 57.5, 85.8, 1, 0.8), strip("f_work_table", 85.0, T_END, 1, 0.8)]))
# Waiter: two straight walks through the kitchen door (x = 4.6). Walk speed from the clip: 1.36 m/s.
WALK_SPEED = 1.496 / 33 * FPS
WAITER_X = 4.6
KITCHEN_Y = ROOM[1] + 0.9       # inside the kitchen, behind the swing door
_out_len = (KITCHEN_Y - 0.6) / WALK_SPEED
_in_len = (KITCHEN_Y - 0.6) / WALK_SPEED
WAITER = dict(tag="waiter", avatar="Business_Male_06", hero=False, sex="m", walks=[
    dict(t0=BEATS["waiter_out_start"], t1=BEATS["waiter_out_start"] + _out_len, start=(WAITER_X, KITCHEN_Y), yaw=0.0,
         door_t=BEATS["waiter_out_start"] + (KITCHEN_Y - ROOM[1]) / WALK_SPEED, door_dir=+1),
    dict(t0=BEATS["waiter_in_start"], t1=BEATS["waiter_in_start"] + _in_len, start=(WAITER_X, 0.6), yaw=math.pi,
         door_t=BEATS["waiter_in_start"] + (ROOM[1] - 0.6) / WALK_SPEED, door_dir=-1),
])

CAST = [MAN, WOMAN] + EXTRAS + [WAITER]
BY_TAG = {c["tag"]: c for c in CAST}


def needed_clip_ranges(c):
    """clip -> (first_frame, last_frame) that must be baked for this character."""
    rng = {}
    for s in c.get("strips", []):
        n = CLIP_LEN[s["clip"]]
        a = s["offset"]
        b = min(n, int(a + (s["t1"] - s["t0"]) * FPS) + 2)
        lo, hi = rng.get(s["clip"], (a, b))
        rng[s["clip"]] = (min(lo, a), max(hi, b))
    return rng
