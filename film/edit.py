"""The edit: every shot, voice line, sound cue and silence, in order.

Timings are derived from the measured length of each voice line, so the cut
follows the narration. `build()` returns a Timeline used by both the picture
renderer (render.py) and the sound mixer (sound.py).
"""
import json

import numpy as np

import look
import shots as S
from config import PHOTOS, RENDERS, STILLS, VOICE
from shots import faces, year_of

D = json.loads((VOICE / "durations.json").read_text())


class Timeline:
    def __init__(self):
        self.items = []          # (start, shot)
        self.t = 0.0
        self.voice = []          # dict(id, t, fx, gain)
        self.sfx = []            # dict(name, t, **kw)
        self.silences = []       # (t0, t1): everything but the voice drops out
        self.beds = []           # dict(kind, t0, t1, level)

    def add(self, shot):
        start = self.t
        self.items.append((start, shot))
        self.t += shot.dur
        return start

    def v(self, lid, t, fx="robot", gain=1.0):
        self.voice.append(dict(id=lid, t=round(t, 3), fx=fx, gain=gain))
        return t + D[lid]

    def s(self, name, t, **kw):
        self.sfx.append(dict(name=name, t=round(t, 3), **kw))

    def bed(self, kind, t0, t1, level=1.0):
        self.beds.append(dict(kind=kind, t0=round(t0, 3), t1=round(t1, 3), level=level))

    @property
    def duration(self):
        return self.t

    def at(self, t):
        starts = [s for s, _ in self.items]
        i = int(np.searchsorted(starts, t, side="right") - 1)
        i = max(0, min(i, len(self.items) - 1))
        s, shot = self.items[i]
        return shot, t - s

    def cues(self):
        return dict(duration=self.t, voice=self.voice, sfx=self.sfx, silences=self.silences, beds=self.beds,
                    shots=[dict(t=round(s, 3), dur=round(sh.dur, 3), kind=type(sh).__name__) for s, sh in self.items])


def slide_title(tl, n, title, **kw):
    t0 = tl.add(S.SlideTitle(n, title, **kw))
    tl.s("slide_change", t0)
    tl.s("beep", t0 + 0.5, freq=1000, dur=0.18, level=0.12)
    return t0


def censor_boxes(name, idx):
    f = faces(name)
    return [f[i] for i in idx]


def build():
    tl = Timeline()

    # ------------------------------------------------------------ tape start, warning
    t0 = tl.add(S.Black(6.0, static=[(0.0, 0.45, 0.85)], osd=[(0.8, 4.0, "PLAY", "tl")]))
    tl.s("vcr_insert", t0)
    tl.bed("hiss", t0 + 0.3, 1e9, 1.0)
    tl.bed("hum", t0 + 0.3, 1e9, 1.0)

    head, l1, l2, l3, body, rule = S.warning_layers()
    t0 = tl.add(S.Black(12.5, layers=[(0.6, 11.3, head, 0.35), (0.9, 11.3, rule, 0.35), (1.8, 11.3, l1, 0.3),
                                      (2.4, 11.3, l2, 0.3), (3.0, 11.3, l3, 0.3), (4.2, 11.3, body, 0.6)]))
    tl.s("beep", t0 + 0.6, freq=880, dur=0.35, level=0.18)
    for k, tt in enumerate((1.8, 2.4, 3.0)):
        tl.s("beep", t0 + tt, freq=1320, dur=0.05, level=0.07)
    tl.bed("drone", t0 + 2.0, t0 + 12.5, 0.35)

    # ------------------------------------------------------------ file title out of the noise
    t0 = tl.add(S.FileTitle(17.0))
    tl.s("static_swell", t0, dur=3.6, level=0.5)
    tl.v("intro", t0 + 4.2)
    tl.bed("drone", t0 + 3.0, t0 + 17.0, 0.5)

    # ------------------------------------------------------------ SLIDE 01 — DEFINITION
    slide_title(tl, 1, "DEFINITION")
    fj = json.loads((RENDERS / "stills" / "forest.json").read_text())
    hb = fj["creature"]
    fig = ((hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2 + 0.06)
    forest = S.Photo(21.4, RENDERS / "stills" / "forest.png", censors=[hb], mode="gray", c0=(0.5, 0.5), c1=fig,
                     z0=1.0, z1=1.55, chrome=(1, "DEFINITION"),
                     caption="FIG. 01-A   FIELD PHOTOGRAPH   //   LOCATION WITHHELD", damage=0.8, pixel=True,
                     pad=0.55, block=5,
                     gradef=lambda im, t: look.grade(im, contrast=1.15, tint=(1.0, 1.0, 1.04)))
    t0 = tl.add(forest)
    e = tl.v("s01a", t0 + 1.2)
    e = tl.v("s01b", e + 1.2)
    tl.bed("drone", t0, t0 + 21.4, 0.55)
    t0 = tl.add(S.BondCard(3.2, forest))
    tl.s("flicker", t0 - 0.5, dur=0.5)
    tl.s("hit", t0, level=0.55)
    tl.v("s01c", t0 + 0.25)
    # the screen flickers just before the word
    forest.fxf = lambda t: ({"static": 0.35, "tracking": 0.6, "tear": 0.3} if t > forest.dur - 0.5 and
                            int(t * 20) % 2 == 0 else {})

    # ------------------------------------------------------------ SLIDE 02 — EARLIEST RECORDS
    slide_title(tl, 2, "EARLIEST RECORDS")
    ch2 = (2, "EARLIEST RECORDS")
    cave = lambda n: STILLS / f"cave_{n}.png"
    seq = [S.Photo(3.2, cave("hunt"), c0=(0.45, 0.5), c1=(0.55, 0.52), z0=1.05, z1=1.15, chrome=ch2,
                   caption="FIG. 02-A   CHAMBER II, NORTH WALL   //   c. 40,000 BP", damage=0.3),
           S.Photo(3.2, cave("fire"), c0=(0.5, 0.55), c1=(0.52, 0.6), z0=1.1, z1=1.2, chrome=ch2,
                   caption="FIG. 02-B   CHAMBER IV   //   c. 32,000 BP", damage=0.3),
           S.Photo(3.0, cave("hands"), c0=(0.5, 0.45), c1=(0.52, 0.55), z0=1.05, z1=1.15, chrome=ch2,
                   caption="FIG. 02-C   SITE 9, RECESS   //   c. 27,000 BP", damage=0.3)]
    t0 = tl.add(S.Sequence(seq))
    for k, sh in enumerate(seq[1:], 1):
        tl.s("slide_change", t0 + sum(x.dur for x in seq[:k]), level=0.6)
    tl.v("s02a", t0 + 0.6)
    tl.bed("drone", t0, t0 + 25, 0.5)
    emb = S.Photo(7.4, cave("embrace"), c0=(0.48, 0.55), c1=(0.45, 0.55), z0=1.0, z1=1.75, chrome=ch2,
                  caption="FIG. 02-D   SITE 9, DETAIL (ENLARGED)", damage=0.3)
    t0 = tl.add(emb)
    tl.s("slide_change", t0, level=0.6)
    tl.v("s02b", t0 + 0.8)
    kneel = S.Photo(4.6, cave("kneel"), c0=(0.5, 0.6), c1=(0.47, 0.62), z0=1.05, z1=1.2, chrome=ch2,
                    caption="FIG. 02-E   SITE 14   //   c. 18,000 BP", damage=0.3,
                    fxf=lambda t: {"tracking": 0.5, "tear": 0.25, "rgb_split": 3} if t > 3.6 else {})
    t0 = tl.add(kneel)
    tl.s("slide_change", t0, level=0.6)
    tl.v("s02c", t0 + 0.5)
    # rapid crops of the tall figure in every panel, ending on the embrace
    crops = [("hunt", (0.73, 0.73), 3.2), ("fire", (0.6, 0.78), 3.0), ("hands", (0.54, 0.74), 2.2),
             ("kneel", (0.55, 0.62), 1.7), ("hunt", (0.73, 0.73), 3.6), ("fire", (0.6, 0.78), 3.4),
             ("hands", (0.54, 0.74), 2.6), ("embrace", (0.46, 0.56), 1.7)]
    cs = [S.Photo(0.34 if i < len(crops) - 1 else 1.9, cave(n), c0=c, c1=c, z0=z, z1=z * 1.04, chrome=ch2,
                  damage=0.5, fxf=lambda t: {"tracking": 0.3} if t < 0.07 else {}) for i, (n, c, z) in enumerate(crops)]
    t1 = tl.add(S.Sequence(cs))
    tl.s("distort_swell", t1 - 0.9, dur=1.2, level=0.45)
    tl.v("s02d", t1 - 0.2, fx="distort")
    for k in range(len(cs) - 1):
        tl.s("tick", t1 + 0.34 * k, level=0.25)

    # ------------------------------------------------------------ SLIDE 03 — HISTORICAL RECORDS
    slide_title(tl, 3, "HISTORICAL RECORDS")
    ch3 = (3, "HISTORICAL RECORDS")
    P = lambda n: PHOTOS / n
    first = [
        S.Photo(2.7, STILLS / "manuscript.png", c0=(0.5, 0.42), c1=(0.49, 0.36), z0=1.25, z1=1.45, chrome=ch3,
                caption="REF. 03-001   ILLUMINATED CODEX, FOLIO 41v   //   c. 1340", damage=0.3),
        S.Photo(2.0, P("Mid1800sSisters.jpg"), censor_boxes("Mid1800sSisters.jpg", [3]), mode="gray",
                c0=(0.5, 0.45), c1=(0.48, 0.42), z0=1.05, z1=1.15, chrome=ch3,
                caption="REF. 03-014   DAGUERREOTYPE   //   c. 1850"),
        S.Photo(2.0, P("PostCivilWarAncestors.jpg"), censor_boxes("PostCivilWarAncestors.jpg", [2]),
                c0=(0.5, 0.4), c1=(0.55, 0.38), z0=1.0, z1=1.1, chrome=ch3,
                caption="REF. 03-022   CABINET CARD   //   c. 1868"),
    ]
    montage = [
        ("Unidentified1855.jpg", [1], "gray"), ("1860Girls.jpg", [1], "gray"), ("1875Olds.jpg", [2], "keep"),
        ("AustriaHungaryWomen1890s.jpg", [3], "keep"), ("scratch_couple.png", [1], "keep"),
        ("GreatGrandparentsIrelandEarly1900s.jpg", [1], "keep"), ("WWIHospital.jpg", [6], "gray"),
        ("Depression.jpg", [2], "gray"), ("MementoMori1865.jpg", [3], "gray"), ("kids_pit.jpg", [7], "gray"),
        ("soldier_kids.jpg", [1], "gray"), ("HalloweenEarly1900s.jpg", [1], "gray"), ("FamilyWithDog.jpg", [3], "keep"),
        ("DutchBabyCoupleEllis.jpg", [0], "keep"), ("1940PAFamily.jpg", [3], "gray"), ("airmen1943.jpg", [1], "gray"),
        ("ServantsBessboroughHouse1908Ireland.jpg", [12], "gray"), ("1890BostonHospital.jpg", [7], "sepia"),
        ("CottonMillWorkers1913.jpg", [1], "gray"), ("poverty.jpg", [1], "gray"), ("dustbowl_people.jpg", [2], "gray"),
        ("1908FamilyPhoto.jpg", [2], "gray"), ("ManPile.jpg", [4], "keep"), ("AppalachianLoggers1901.jpg", [5], "gray"),
        ("scratch_girl.png", [0], "keep"), ("autochrome_crown.png", [0], "aged"), ("scratch_boy.png", [0], "keep"),
        ("NorwegianBride1920s.jpg", [0], "gray"), ("GreatAunt1920.jpg", [0], "gray"), ("1870Girl.jpg", [0], "keep"),
        ("IrishLate1800s.jpg", [0], "keep"), ("1897BlindmansBluff.jpg", [1], "keep"),
        ("autochrome_garden.png", [1], "aged"), ("FinnishPeasant1867.jpg", [0], "keep"),
        ("ArmisticeDay1918.jpg", [1], "gray"), ("1925Girl.jpg", [0], "keep"), ("Mid1800sSisters.jpg", [0], "gray"),
        ("1860Girls.jpg", [2], "gray"), ("WWIIPeeps.jpg", [1], "gray"), ("OregonTrail1870s.jpg", [2], "gray"),
    ]
    durs = [max(1 / 15, 0.95 * 0.83 ** i) for i in range(len(montage))]
    fast = []
    for i, ((n, idx, mode), d) in enumerate(zip(montage, durs)):
        bx = censor_boxes(n, idx)
        c = ((bx[0][0] + bx[0][2]) / 2, (bx[0][1] + bx[0][3]) / 2)
        zc = (0.5 + (c[0] - 0.5) * 0.5, 0.5 + (c[1] - 0.5) * 0.5)
        fast.append(S.Photo(d, P(n), bx, mode=mode, c0=zc, c1=zc, z0=1.05 + 0.04 * (i % 3), z1=1.1 + 0.04 * (i % 3),
                            chrome=ch3, caption=f"REF. 03-{40 + i * 7:03d}   //   {year_of(n)}", damage=0.9,
                            pixel=(i % 5 == 4)))
    t0 = tl.add(S.Sequence(first + fast))
    tl.bed("drone", t0, t0 + 30, 0.6)
    tl.v("s03a", t0 + 0.4)
    t_fast = t0 + sum(x.dur for x in first)
    acc = t0
    for x in first + fast:
        tl.s("tick", acc, level=0.3 if x.dur > 0.2 else 0.18)
        acc += x.dur
    tl.v("s03b", t_fast + 0.3)
    tl.s("riser", t_fast, dur=acc - t_fast, level=0.5)
    # hard stop: one family, one face
    fam = faces("1920sFamilyPhoto.jpg")
    target = fam[4]
    tc = ((target[0] + target[2]) / 2, (target[1] + target[3]) / 2)

    def reveal(img, t, rng, v, at=10.2):
        # for one frame the bar is not there: under it, nothing — a smooth, blank face
        if at <= t < at + 1 / 30 + 1e-3:
            x0, y0, x1, y1 = [int(q) for q in v.box(target)]
            pad = int((x1 - x0) * 0.25)
            roi = img[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            if roi.size:
                img[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = cv2_blur(roi) * 1.12
        return img

    family = S.Photo(11.6, P("1920sFamilyPhoto.jpg"), [], mode="keep", c0=(0.5, 0.5),
                     c1=(0.5 + (tc[0] - 0.5) * 0.9, 0.5 + (tc[1] - 0.5) * 0.9), z0=1.0, z1=2.1, chrome=ch3,
                     caption="REF. 03-311   FAMILY PORTRAIT   //   c. 1921", damage=0.5)

    def fam_extra(img, t, rng, v):
        img = reveal(img, t, rng, v)
        if not (10.2 <= t < 10.2 + 1 / 30 + 1e-3):
            img = look.censor(img, v.box(target))
        return img
    family.extra = fam_extra
    t0 = tl.add(family)
    tl.s("hit", t0, level=0.5)
    tl.s("stop_noise", t0 - 0.02)
    tl.v("s03c", t0 + 1.0)
    tl.s("sub_pulse", t0 + 10.2, level=0.4)

    # ------------------------------------------------------------ SLIDE 04 — FIRST DOCUMENTED CONTACT
    slide_title(tl, 4, "FIRST DOCUMENTED CONTACT")
    import p04 as Q
    cont = S.Containment(hold=0.6 + D["s04d"] + 1.8)
    t0 = tl.add(cont)
    tl.bed("roomtone", t0, t0 + Q.BLACKOUT[0], 1.0)          # the hum dies with the light
    tl.bed("drone", t0, t0 + Q.STARE, 0.35)
    tl.bed("drone", t0 + Q.FREEZE, t0 + cont.dur, 0.7)
    tl.v("s04a", t0 + 1.0)
    tl.s("beep", t0 + 3.0, freq=1600, dur=0.08, level=0.12)
    tl.s("latch", t0 + Q.LATCH)
    tl.s("door", t0 + Q.DOOR_OPEN[0] - 0.45)
    tl.s("steps", t0 + Q.WALK1[0] + 0.2, end=t0 + Q.WALK1[1], interval=0.8)
    tl.s("steps", t0 + Q.WALK2[0] + 0.2, end=t0 + Q.WALK2[1], interval=0.87)
    tl.s("rustle", t0 + Q.KNEEL[0] + 0.2, dur=1.2, level=0.11)
    tl.v("s04b", t0 + 12.3)
    tl.s("rustle", t0 + Q.REACH[0], dur=0.7, level=0.07)
    tl.s("rustle", t0 + Q.RETRACT[0], dur=0.6, level=0.08)
    tl.s("glitch", t0 + Q.SKIP - 0.02, dur=0.2, level=0.6)
    tl.v("s04c", t0 + Q.SKIP + 0.4)
    for a, b in Q.FLICKERS:
        tl.s("flicker", t0 + a - 0.02, dur=b - a + 0.06)
    tl.s("power_down", t0 + Q.BLACKOUT[0])
    tl.silences.append((t0 + Q.STARE, t0 + Q.ZOOM2))      # it is looking at us; nothing makes a sound
    for k, z in enumerate((Q.ZOOM2, Q.ZOOM4, Q.ZOOM8)):
        tl.s("zoom_click", t0 + z, level=0.45 + 0.15 * k)
    tl.s("sting", t0 + Q.FREEZE, level=0.7)
    tl.s("freeze", t0 + Q.FREEZE)
    tl.v("s04d", t0 + Q.FREEZE + 0.6)

    # ------------------------------------------------------------ SLIDE 05 — BEHAVIOR
    slide_title(tl, 5, "BEHAVIOR")
    t_move = 10.2
    t_a = 11.6
    t_b = t_a + D["s05a"] + 1.3
    t_gl = t_b + D["s05b"] + 0.2
    t_c = t_gl + 0.7
    beh = S.Behaviors(t_c + D["s05c"] + 1.5, glitch=[(t_gl, t_gl + 0.55)], flash=[t_gl + 0.2, t_gl + 0.33])
    t0 = tl.add(beh)
    for i in range(9):
        tl.s("type_burst", t0 + 1.0 + i * 0.85, n=6, level=0.2)
    tl.bed("drone", t0, t0 + beh.dur, 0.45)
    tl.bed("duck", t0 + 9.0, t0 + beh.dur, 0.55)          # "the audio gets slightly lower"
    tl.v("s05a", t0 + t_a)
    tl.v("s05b", t0 + t_b)
    tl.s("glitch", t0 + t_gl, dur=0.55, level=0.7)
    tl.v("s05c", t0 + t_c)

    # ------------------------------------------------------------ SLIDE 06 — INTERACTION PROTOCOL
    slide_title(tl, 6, "INTERACTION PROTOCOL")
    times = []
    t = 0.8 + D["s06a"] + 0.7
    for i in range(1, 8):
        times.append(t)
        t += 0.25 + D[f"r0{i}"] + 0.6
    t8 = t + 0.4
    times.append(t8)
    t_black = t8 + 3.6
    t_none = t_black + 2.7
    proto = S.Protocol(t_none + D["s06b"] + 1.8, times, t_black)
    t0 = tl.add(proto)
    tl.bed("drone", t0, t0 + t_black, 0.4)
    tl.v("s06a", t0 + 0.8)
    for i, tr in enumerate(times[:7], 1):
        tl.s("type_burst", t0 + tr, n=4, level=0.15)
        tl.v(f"r0{i}", t0 + tr + 0.25)
    tl.s("type_burst", t0 + t8, n=4, level=0.15)
    tl.silences.append((t0 + t_black, t0 + t_none))
    tl.v("s06b", t0 + t_none)
    tl.silences.append((t0 + t_none, t0 + proto.dur))

    # ------------------------------------------------------------ SLIDE 07 — INCIDENT 12
    slide_title(tl, 7, "INCIDENT 12")
    corr = S.Photo(7.0, RENDERS / "stills" / "corridor.png", mode="keep", c0=(0.5, 0.5), c1=(0.5, 0.48), z0=1.0,
                   z1=1.15, chrome=(7, "INCIDENT 12"), caption="FIG. 07-A   SUBLEVEL 3, EAST CORRIDOR   //   1997",
                   damage=0.4, gradef=lambda im, t: look.grade(im, contrast=1.1, sat=0.6, tint=(0.96, 1.02, 0.98)))
    t0 = tl.add(corr)
    tl.v("s07a", t0 + 0.8)
    tl.bed("drone", t0, t0 + 50, 0.45)
    cell = S.Cell(lapse=4.6, real=(9.0, 21.0), distort=3.6, post_hold=1.4)
    t0 = tl.add(cell)
    tl.bed("roomtone", t0, t0 + cell.t_real_end + 0.5, 0.8)
    tl.s("ff_whine", t0, dur=cell.lapse, level=0.14)
    tl.v("s07b", t0 + 0.6)
    tl.v("s07c", t0 + cell.lapse + 7.4)
    td = t0 + cell.t_real_end
    tl.s("distort_swell", td, dur=1.0, level=0.5)
    tl.silences.append((td + 0.4, td + cell.distort))
    tl.v("s07d", td + 1.0, fx="tape", gain=0.55)
    tl.silences.append((td + cell.distort, t0 + cell.dur))
    t0 = tl.add(S.EmptyCell(1.2 + D["s07e"] + 1.0 + D["s07f"] + 1.6))
    tl.bed("roomtone", t0, t0 + 1.2 + D["s07e"] + 1.0 + D["s07f"] + 1.6, 0.6)
    e = tl.v("s07e", t0 + 1.2)
    tl.v("s07f", e + 1.0)

    # ------------------------------------------------------------ SLIDE 08 — OBSERVATION
    slide_title(tl, 8, "OBSERVATION")
    cj = json.loads((RENDERS / "stills" / "corridor_end.json").read_text())["creature"]
    cc = ((cj[0] + cj[2]) / 2, (cj[1] + cj[3]) / 2 + 0.05)
    obs = S.Photo(11.5, RENDERS / "stills" / "corridor_end.png", mode="keep", c0=(0.5, 0.5),
                  c1=(0.5 + (cc[0] - 0.5) * 0.8, 0.5 + (cc[1] - 0.5) * 0.8), z0=1.0, z1=1.7, chrome=(8, "OBSERVATION"),
                  caption="FIG. 08-A   SUBLEVEL 3, EAST CORRIDOR   //   1997", damage=0.5,
                  gradef=lambda im, t: look.grade(im, contrast=1.15, sat=0.55, tint=(0.96, 1.02, 0.98)),
                  fxf=lambda t: {"tracking": 0.6, "tear": 0.35, "static": 0.2} if 5.5 <= t < 5.8 else {})
    t0 = tl.add(obs)
    tl.bed("drone", t0, t0 + obs.dur, 0.55)
    tl.v("s08a", t0 + 1.0)
    tl.s("glitch", t0 + 5.5, dur=0.3, level=0.5)
    tl.v("s08b", t0 + 7.0)

    # ------------------------------------------------------------ SLIDE 09 — CLASSIFICATION
    slide_title(tl, 9, "CLASSIFICATION")
    ev = [(0.6, 0, "PASIÓN", "type", 0.09), (2.2, 1, "ORIGIN: UNKNOWN", "type", 0.05),
          (3.6, 2, "OBJECTIVE: UNKNOWN", "type", 0.05), (7.6, 3, "BEHAVIORAL PATTERN: LOVE", "type", 0.05)]
    t_fl = 10.6
    ev += [(12.0, 9, "AUTOMATIC CORRECTION", "type", 0.0001), (13.2, 3, "BEHAVIORAL PATTERN: ", "back", 0.09),
           (13.7, 3, "BEHAVIORAL PATTERN: NEED FOR LOVE", "type", 0.07)]
    cl = S.Classification(18.0, ev)
    cl.flicker = [(t_fl, t_fl + 1.2)]
    t0 = tl.add(cl)
    tl.bed("drone", t0, t0 + 18, 0.4)
    for (te, row, text, mode, sp) in ev:
        if mode == "type" and row != 9:
            tl.s("type_burst", t0 + te, n=len(text), interval=sp, level=0.18)
        if mode == "back":
            tl.s("type_burst", t0 + te, n=4, interval=sp, level=0.14)
    tl.s("glitch", t0 + t_fl, dur=1.2, level=0.25)
    tl.s("alarm", t0 + 12.0, level=0.18)

    # ------------------------------------------------------------ SLIDE 10 — FINAL INSTRUCTION
    slide_title(tl, 10, "FINAL INSTRUCTION", glitchy=True)
    a = 1.0
    b = a + D["s10a"] + 1.1
    c = b + D["s10b"] + 1.4
    d = c + D["s10c"] + 0.85
    e_ = d + D["s10d"] + 0.85
    f = e_ + D["s10e"] + 0.9
    g = f + D["s10f"] + 2.0          # silence before the human voice
    end = g + D["s10g"] + 0.15
    hall = S.Hallway(end + 0.01,
                     distort=[(a + D["s10a"] + 0.1, b - 0.05, 0.45), (b + D["s10b"] + 0.1, c - 0.05, 0.85),
                              (e_ - 0.4, f + D["s10f"] + 0.1, lambda t, e0=e_ - 0.4, e1=f + D["s10f"]:
                               0.15 + 0.75 * (t - e0) / (e1 - e0))],
                     flashes=[b + D["s10b"] + 0.5, e_ + 0.6, f - 0.3, f + D["s10f"] - 0.2],
                     clean=(f + D["s10f"] + 0.15, end), t_cut=end)
    t0 = tl.add(hall)
    tl.bed("drone", t0, t0 + f + D["s10f"], 0.6)
    tl.v("s10a", t0 + a, fx="glitch1")
    tl.s("static_burst", t0 + a + D["s10a"] + 0.1, dur=1.0, level=0.45)
    tl.v("s10b", t0 + b, fx="glitch2")
    tl.s("static_burst", t0 + b + D["s10b"] + 0.1, dur=1.3, level=0.8)
    tl.v("s10c", t0 + c, fx="glitch2")
    tl.v("s10d", t0 + d, fx="glitch2")
    tl.v("s10e", t0 + e_, fx="glitch3")
    tl.s("riser", t0 + e_ - 0.4, dur=f + D["s10f"] - e_ + 0.5, level=0.5)
    tl.v("s10f", t0 + f, fx="drag")
    for ft in hall.flashes:
        tl.s("flash_hit", t0 + ft, level=0.5)
    tl.silences.append((t0 + f + D["s10f"] + 0.12, t0 + end + 0.2))
    tl.v("s10g", t0 + g, fx="reveal")

    # ------------------------------------------------------------ END
    te, tc, ts = 1.3, 8.5, 15.5
    tw = ts + 1.6
    tstop = tw + 5.2
    endc = S.EndCards(tstop + 2.5, te, tc, ts, tw, tstop)
    t0 = tl.add(endc)
    tl.silences.append((t0, t0 + tc))
    tl.s("beep", t0 + te, freq=660, dur=0.4, level=0.12)
    tl.s("glitch", t0 + tc, dur=0.4, level=0.5)
    tl.bed("drone", t0 + tc, t0 + ts, 0.5)
    tl.s("type_burst", t0 + tc + 2.0, n=len(endc.reason), interval=0.055, level=0.18)
    tl.s("static_swell", t0 + ts, dur=1.6, level=0.7, hold=True)
    tl.silences.append((t0 + tw, t0 + endc.dur))
    tl.v("tail", t0 + tw + 0.9, fx="whisper", gain=0.75)
    tl.s("vcr_stop", t0 + tstop)
    return tl


def cv2_blur(roi):
    import cv2
    return cv2.GaussianBlur(roi, (0, 0), max(2.0, roi.shape[1] / 6))


if __name__ == "__main__":
    tl = build()
    print(f"duration {tl.duration:.1f}s  ({tl.duration / 60:.2f} min), {len(tl.items)} shots, "
          f"{len(tl.voice)} voice cues, {len(tl.sfx)} sfx")
    (VOICE.parent / "cues.json").write_text(json.dumps(tl.cues(), indent=1))
