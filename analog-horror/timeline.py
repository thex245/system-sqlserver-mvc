"""Master timeline for TAPE 1 — "I DO".  All times are FILM seconds unless noted.

Shared by the Blender assembly, the audio mix and the CCTV post-processing. Blender runs at
30 fps; CAM 04 records at 15 fps, so only even film frames are rendered and each is held twice.
"""
FPS = 30
CCTV_STEP = 1  # every frame is rendered (30 fps CCTV)

# Selected dialogue takes (D:\VAMA_work\audio\takes\<take>.wav); see audio/tts_generate.py
TAKES = {
    "M01": "M01_1", "W01": "W01_3", "M02": "M02_1", "W02": "W02_0", "M03": "M03_0", "W03": "W03_3",
    "M04": "M04_0", "M05": "M05_3", "W04": "W04_1", "M06": "M06_0", "M07": "M07_1", "M08": "extra/M08_7",
    "W05": "W05_0", "M09": "extra/M09_6", "M10": "M10_3", "W06": "W06_0", "W07": "W07_1",
}
SPEAKER = {k: ("man" if k.startswith("M") else "woman") for k in TAKES}

# Segments: (name, film_start, film_end, clock_at_start "HH:MM:SS.s" or None)
SEGMENTS = [
    ("black",     0.0,   3.0, None),
    ("establish", 3.0,  41.0, "21:47:12.0"),
    ("dialogue",  41.0,  79.5, "21:49:30.0"),
    ("standing",  79.5,  99.5, "21:51:07.2"),   # image returns 0.8 s in, at 21:51:08
    ("ring",      99.5, 115.5, "21:51:41.0"),   # ring removal starts at 21:51:42
    ("freeze",   115.5, 121.5, None),           # frozen picture, clock frozen/glitching
    ("empty",    121.5, 146.5, "21:51:47.0"),   # interference at 21:52:03
    ("end",      146.5, 153.0, None),
]
SEG = {s[0]: s for s in SEGMENTS}
FREEZE_AT = 115.5          # film time whose picture is frozen
FILM_END = 153.0


def seg_t(name, local):
    return SEG[name][1] + local


# Dialogue cues: line id -> film time at which SPEECH begins (leading silence is trimmed in the mix)
LINES = {
    "M01": seg_t("dialogue", 6.0),
    "W01": seg_t("dialogue", 8.9),
    "M02": seg_t("dialogue", 11.0),
    "W02": seg_t("dialogue", 16.5),
    "M03": seg_t("dialogue", 22.5),
    "W03": seg_t("dialogue", 30.0),
    "M04": seg_t("dialogue", 33.0),
    "M05": seg_t("standing", 1.6),
    "W04": seg_t("standing", 3.7),
    "M06": seg_t("standing", 5.7),
    "M07": seg_t("standing", 10.2),
    "M08": seg_t("ring", 5.2),
    "W05": seg_t("ring", 9.8),
    "M09": seg_t("ring", 11.6),
    "M10": seg_t("ring", 13.0),
    "W06": seg_t("freeze", 2.2),     # buried in the distortion
    "W07": seg_t("empty", 22.0),
}

# Interference / glitch events for post (film time, duration, kind)
GLITCHES = [
    (3.0, 0.35, "sync"),            # picture locks in
    (21.0, 0.12, "tear"),
    (33.4, 0.20, "tracking"),
    (41.0, 0.30, "skip"),           # DVR skip 21:47:50 -> 21:49:30
    (60.1, 0.10, "tear"),
    (79.5, 0.80, "interference"),   # man is standing when it returns
    (99.5, 0.25, "skip"),
    (115.5, 6.0, "freeze"),
    (121.5, 0.40, "return"),
    (131.0, 0.10, "tear"),
    (137.5, 1.60, "interference"),  # 21:52:03 — she appears
    (146.5, 0.6, "tape_end"),
]

# Story beats used by the animation (film seconds)
BEATS = {
    "waiter_out_start": seg_t("establish", 6.0),     # waiter leaves kitchen toward the camera
    "car_pass_1": seg_t("establish", 19.0),
    "man_looks_at_camera": seg_t("establish", 26.0),  # 2.5 s stare into the lens
    "car_pass_2": seg_t("standing", 14.0),
    "waiter_in_start": seg_t("standing", 8.0),       # waiter walks back to the kitchen, ignoring them
    "head_tilt": seg_t("dialogue", 8.2),
    "look_at_hand": seg_t("dialogue", 25.2),
    "smile_off": seg_t("dialogue", 34.9),
    "ring_off_start": seg_t("ring", 1.0),
    "ring_on_table": seg_t("ring", 4.6),
    "smile_back": seg_t("ring", 7.8),
    "slam": seg_t("ring", 12.85),
    "she_appears": seg_t("empty", 17.1),
    "final_blink": seg_t("empty", 24.0),
}


def frame(t):
    return int(round(t * FPS)) + 1


def clock_at(t):
    """CCTV clock string at film time t (None during black/freeze/end)."""
    for name, a, b, c in SEGMENTS:
        if a <= t < b:
            if c is None:
                return None
            h, m, s = c.split(":")
            secs = int(h) * 3600 + int(m) * 60 + float(s) + (t - a)
            hh, rem = divmod(int(secs), 3600)
            mm, ss = divmod(rem, 60)
            return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return None
