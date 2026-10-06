"""Every visual beat of the film as a Shot: frame(t, rng) -> HxWx3 float image
(the picture as recorded on tape), fx(t) -> VHS parameter overrides, and
post(img, t, rng) for things the VCR itself draws on top (PLAY / STOP).
"""
import functools
import json
import math
import re

import cv2
import numpy as np

import look
from config import H, PHOTOS, RENDERS, STILLS, W
from look import TextLayer, font, View

OSD_BLUE = (90, 140, 255)


class Shot:
    def __init__(self, dur):
        self.dur = dur

    def frame(self, t, rng):
        return look.blank()

    def fx(self, t):
        return {}

    def post(self, img, t, rng):
        return img


def env(t, a, b, fade=0.25):
    """1 inside [a, b] with linear fades of `fade` seconds."""
    if t < a - fade or t > b + fade:
        return 0.0
    if t < a:
        return 1 - (a - t) / fade
    if t > b:
        return 1 - (t - b) / fade
    return 1.0


def pulse(t, at, length):
    return 1.0 if at <= t < at + length else 0.0


# ------------------------------------------------------------------ VCR on-screen display (post-VHS)
@functools.lru_cache(8)
def _osd_layer(text, pos):
    L = TextLayer()
    f = font("osd", 40)
    x, y = {"tl": (34, 24), "tr": (W - 34, 24)}[pos]
    anchor = "la" if pos == "tl" else "ra"
    for dx, dy in ((2, 2), (-1, 0), (1, 0), (0, 1)):
        L.d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0, 255), anchor=anchor)
    L.d.text((x, y), text, font=f, fill=(235, 235, 235, 255), anchor=anchor)
    return L


def vcr_osd(img, text, pos="tl"):
    return _osd_layer(text, pos).over(img)


@functools.lru_cache(4)
def _osd_icon(kind):
    L = TextLayer()
    f = font("osd", 40)
    x = 34 + int(f.getlength({"play": "PLAY ", "stop": "STOP "}[kind]))
    for col, d in (((0, 0, 0, 255), 2), ((235, 235, 235, 255), 0)):
        if kind == "play":
            L.d.polygon([(x + d, 33 + d), (x + 22 + d, 45 + d), (x + d, 57 + d)], fill=col)
        else:
            L.d.rectangle([x + d, 35 + d, x + 20 + d, 55 + d], fill=col)
    return L


# ------------------------------------------------------------------ basic cards
class Black(Shot):
    def __init__(self, dur, layers=(), static=None, osd=None):
        super().__init__(dur)
        self.layers = layers          # [(t0, t1, TextLayer, fade)]
        self.static = static          # [(t0, t1, amount)]
        self.osd = osd or []          # [(t0, t1, text, pos)]

    def frame(self, t, rng):
        img = look.blank()
        for (a, b, L, fade) in self.layers:
            e = env(t, a, b, fade)
            if e > 0:
                img = L.over(img, e)
        return img

    def fx(self, t):
        p = {}
        for (a, b, amt) in (self.static or []):
            if a <= t < b:
                p["static"] = amt if not callable(amt) else amt(t)
                p["tracking"] = 0.6
        return p

    def post(self, img, t, rng):
        for (a, b, text, pos) in self.osd:
            if a <= t < b:
                img = vcr_osd(img, text, pos)
                if text == "PLAY":
                    img = _osd_icon("play").over(img)
        return img


def warning_layers():
    head = TextLayer().text((W // 2, 92), "[NOTICE — RESTRICTED ACCESS]", font("monob", 26), fill=look.RED, anchor="mm")
    l1 = TextLayer().text((W // 2, 178), "CLASSIFIED DOCUMENT", font("monob", 23), anchor="mm")
    l2 = TextLayer().text((W // 2, 214), "PROPERTY OF THE FEDERAL GOVERNMENT", font("monob", 23), anchor="mm")
    l3 = TextLayer().text((W // 2, 250), "ACCESS LEVEL: B.C.", font("monob", 23), fill=look.AMBER, anchor="mm")
    body = TextLayer()
    f = font("mono", 18)
    para = ("Reproduction, copying or distribution of this material without authorization "
            "constitutes a violation of the National Security Act.")
    for i, ln in enumerate(look.wrap(para, f, 560)):
        body.text((W // 2, 330 + i * 28), ln, f, fill=(200, 200, 196), anchor="mm")
    rule = TextLayer().rect([110, 130, W - 110, 132], fill=(150, 40, 35, 255)).rect(
        [110, 290, W - 110, 292], fill=(150, 40, 35, 255))
    return head, l1, l2, l3, body, rule


class FileTitle(Shot):
    """[FILE: B.C. — HISTORY AND BEHAVIOR] — emerges out of tape noise."""

    def __init__(self, dur, static_in=3.4):
        super().__init__(dur)
        self.static_in = static_in
        L = TextLayer()
        look.emblem(L, W // 2, 168, 74)
        L.text((W // 2, 296), "[FILE: B.C. — HISTORY AND BEHAVIOR]", font("head", 34), anchor="mm")
        L.rect([140, 324, W - 140, 326], fill=(120, 150, 180, 255))
        L.text((W // 2, 352), "INSTRUCTIONAL SERIES  ·  FOR AUTHORIZED PERSONNEL ONLY", font("mono", 15),
               fill=(160, 180, 200), anchor="mm")
        L.text((W // 2, 452), "TAPE B.C.   ·   1 OF 1", font("monob", 15), fill=(130, 150, 170), anchor="mm")
        self.L = L

    def frame(self, t, rng):
        img = self.L.over(look.slide_bg())
        fade = look.ease((t - 1.4) / 2.6)
        return img * fade

    def fx(self, t):
        s = self.static_in
        if t < 0.9:
            return {"static": t / 0.9 * 0.9, "tracking": 0.8}
        if t < s:
            return {"static": 0.9 * (1 - look.ease((t - 0.9) / (s - 0.9))), "tracking": 0.8 * (1 - (t - 0.9) / (s - 0.9))}
        return {}


class SlideTitle(Shot):
    def __init__(self, n, title, dur=2.8, glitchy=False):
        super().__init__(dur)
        self.glitchy = glitchy
        L = TextLayer()
        L.text((70, 220), f"SLIDE {n:02d}", font("monob", 24), fill=(150, 175, 200), shadow=False)
        L.rect([70, 256, 70 + 64, 260], fill=(200, 60, 50, 255))
        L.text((70, 270), title, font("head", 48 if len(title) < 22 else 40), shadow=True)
        look.emblem(L, W - 80, H - 80, 36, color=(110, 130, 150))
        self.L = L

    def frame(self, t, rng):
        img = look.slide_bg().copy()
        wipe = look.ease(t / 0.45)
        cut = int(W * wipe)
        img2 = self.L.over(img)
        img[:, :cut] = img2[:, :cut]
        return img

    def fx(self, t):
        p = {}
        if t < 0.12:
            p.update(static=0.5, tracking=0.5)
        if self.glitchy and 1.3 < t < 1.6:
            p.update(tear=0.6, rgb_split=4, tracking=0.6)
        return p


# ------------------------------------------------------------------ photographs
FACES = None


def faces(name):
    global FACES
    if FACES is None:
        FACES = json.loads((STILLS / "faces.json").read_text())
    return [b[:4] for b in FACES[name]]


@functools.lru_cache(64)
def photo(path, mode="keep", max_side=1500):
    im = look.load(path)
    h, w = im.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    if mode == "sepia":
        g = im @ np.array([0.299, 0.587, 0.114], np.float32)
        im = np.clip(g[..., None] * np.array([1.06, 0.95, 0.78], np.float32) + 0.02, 0, 1)
    elif mode == "gray":
        g = im @ np.array([0.299, 0.587, 0.114], np.float32)
        im = np.repeat(g[..., None], 3, axis=2)
    elif mode == "aged":    # keep colour but push toward an old print
        im = look.grade(im, contrast=0.95, sat=0.55, tint=(1.04, 0.98, 0.86))
    return np.ascontiguousarray(im.astype(np.float32))


@functools.lru_cache(32)
def caption_layer(chrome, caption):
    L = look.slide_chrome(*chrome) if chrome else TextLayer()
    if caption:
        f = font("mono", 13)
        w = int(f.getlength(caption)) + 24
        L.rect([16, H - 66, 16 + w, H - 40], fill=(0, 0, 0, 170))
        L.text((28, H - 53), caption, f, fill=(215, 215, 205), anchor="lm", shadow=False)
    return L


class Photo(Shot):
    """A still with Ken Burns motion, censor bars over chosen faces, slide chrome and a caption."""

    def __init__(self, dur, path, censors=(), mode="keep", c0=(0.5, 0.5), c1=(0.5, 0.5), z0=1.0, z1=1.08,
                 chrome=None, caption="", damage=0.6, gradef=None, extra=None, fxf=None, pixel=False, pad=0.18,
                 block=12):
        super().__init__(dur)
        self.path, self.mode = path, mode
        self.censors = list(censors)
        self.c0, self.c1, self.z0, self.z1 = c0, c1, z0, z1
        self.chrome, self.caption = chrome, caption
        self.damage, self.gradef, self.extra, self.fxf = damage, gradef, extra, fxf
        self.pixel, self.pad, self.block = pixel, pad, block

    def view(self, t):
        return look.kenburns(photo(self.path, self.mode), t, self.dur, self.c0, self.c1, self.z0, self.z1)

    def frame(self, t, rng):
        v = self.view(t)
        img = v.render()
        if self.gradef:
            img = self.gradef(img, t)
        img = look.film_damage(img, rng, self.damage) if self.damage else img
        for b in self.censors:
            box = v.box(b)
            if self.pixel:
                img = look.pixelate(img, box, self.block, pad=self.pad)
            else:
                img = look.censor(img, box, pad=self.pad)
        if self.extra:
            img = self.extra(img, t, rng, v)
        return caption_layer(self.chrome, self.caption).over(img)

    def fx(self, t):
        p = {}
        if t < 2 / 30:
            p.update(static=0.35, tracking=0.4)
        if self.fxf:
            p.update(self.fxf(t))
        return p


class Sequence(Shot):
    """Plays sub-shots back to back (used for montages)."""

    def __init__(self, shots, cut_flash=True):
        super().__init__(sum(s.dur for s in shots))
        self.shots = shots
        self.starts = np.cumsum([0] + [s.dur for s in shots])[:-1]
        self.cut_flash = cut_flash

    def _at(self, t):
        i = int(np.searchsorted(self.starts, t, side="right") - 1)
        i = max(0, min(i, len(self.shots) - 1))
        return self.shots[i], t - self.starts[i]

    def frame(self, t, rng):
        s, lt = self._at(t)
        return s.frame(lt, rng)

    def fx(self, t):
        s, lt = self._at(t)
        return s.fx(lt)

    def post(self, img, t, rng):
        s, lt = self._at(t)
        return s.post(img, lt, rng)


def year_of(name):
    m = re.search(r"(1[89]\d\d)", name)
    return f"c. {m.group(1)}" if m else "UNDATED"


# ------------------------------------------------------------------ CCTV
def barrel(img, k=0.08):
    yy, xx = look._grid()
    r2 = xx ** 2 + yy ** 2
    f = 1 + k * r2
    mx = ((xx * f) / 2 + 0.5) * W
    my = ((yy * f) / 2 + 0.5) * H
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT)


def cctv_grade(img, tint=(0.86, 1.0, 0.84)):
    g = img @ np.array([0.299, 0.587, 0.114], np.float32)
    g = np.clip((g - 0.03) * 1.25, 0, 1) ** 0.9
    return np.clip(g[..., None] * np.array(tint, np.float32), 0, 1)


def cctv_osd(lines):
    """lines: [(x, y, text, anchor)] in VT323 white with a black edge."""
    L = TextLayer()
    f = font("osd", 30)
    for x, y, s, a in lines:
        for dx, dy in ((2, 2), (-1, -1), (1, -1), (-1, 1)):
            L.d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0, 255), anchor=a)
        L.d.text((x, y), s, font=f, fill=(240, 240, 240, 255), anchor=a)
    return L


@functools.lru_cache(400)
def footage_frame(path):
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:          # not rendered yet: placeholder so the edit can be previewed
        return np.zeros((600, 800, 3), np.float32)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def clock(base_h, base_m, base_s, secs):
    tot = int(base_h * 3600 + base_m * 60 + base_s + secs) % 86400
    return f"{tot // 3600:02d}:{tot // 60 % 60:02d}:{tot % 60:02d}"


class Containment(Shot):
    """SLIDE 04: CCTV of P-04, digital enhance onto its face, freeze."""

    def __init__(self, t_enhance=20.0, t_freeze=22.4, hold=3.6):
        self.te, self.tf = t_enhance, t_freeze
        super().__init__(t_freeze + hold)
        d = RENDERS / "containment"
        self.d1, self.d2 = d / "cam1", d / "cam2"
        tp = self.d1 / "track_1_721.json"
        tr = json.loads(tp.read_text()) if tp.exists() else {}
        self.track = {int(k): v["creature"] for k, v in tr.items()}

    @staticmethod
    def fnum(ft, lo=1, hi=721):
        f = 1 + 2 * int(round(ft * 15))
        return max(lo, min(hi, f))

    def frame(self, t, rng):
        ft = min(t, self.tf)
        if t < self.te + 0.8:
            f = self.fnum(ft)
            src = footage_frame(self.d1 / f"{f:04d}.png")
            if t >= self.te:   # digital zoom toward the face
                b = self.track.get(f, [0.5, 0.4, 0.55, 0.45])
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                x = look.ease((t - self.te) / 0.8)
                v = View(src, (0.5 + (cx - 0.5) * x, 0.5 + (cy - 0.5) * x), 1 + 4.5 * x)
                img = v.render()
                img = cv2.resize(cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (W, H),
                                 interpolation=cv2.INTER_NEAREST) * 0.5 + img * 0.5
            else:
                img = View(src).render()
            if t >= self.te + 0.55:
                f2 = self.fnum(ft, 541, 721)
                img2 = View(footage_frame(self.d2 / f"{f2:04d}.png")).render()
                a = look.ease((t - self.te - 0.55) / 0.25)
                img = img * (1 - a) + img2 * a
        else:
            f2 = self.fnum(ft, 541, 721)
            src = footage_frame(self.d2 / f"{f2:04d}.png")
            z = 1.0 if t < self.tf else 1.0 + 0.22 * look.ease((t - self.tf) / (self.dur - self.tf))
            img = View(src, (0.52, 0.47), z).render()
        img = cctv_grade(barrel(img))
        enhanced = t >= self.te + 0.55
        lines = [(26, 22, "CAM 01", "la"), (W - 26, 22, "09-17-1986", "ra"),
                 (W - 26, 50, clock(2, 41, 7, ft), "ra"), (26, H - 56, "C-WING / CONTAINMENT 4", "la")]
        if enhanced:
            lines.append((26, 50, "DIGITAL ENHANCE x4", "la"))
        if t >= self.tf:
            lines.append((W // 2, 22, "FRAME HOLD", "ma"))
        img = _osd_cached(tuple(lines)).over(img)
        # P-04 tag
        if 3.0 <= t < 8.5 and not enhanced:
            if not (t < 3.6 and int(t * 6) % 2):
                f = self.fnum(ft)
                b = self.track.get(f)
                if b:
                    v = View(footage_frame(self.d1 / f"{f:04d}.png"))
                    hb = v.box(b)
                    cx = (hb[0] + hb[2]) / 2
                    hh = hb[3] - hb[1]
                    x0, y0 = int(cx - hh * 2.2), int(hb[1] - hh * 0.6)
                    x1, y1 = int(cx + hh * 2.2), int(hb[3] + hh * 3.6)
                    cv2.rectangle(img, (x0, y0), (x1, y1), (0.95, 0.95, 0.9), 1)
                    img = _tag_layer(x1 + 6, y0).over(img)
        return img

    def fx(self, t):
        p = {"noise": 0.06, "streak": 0.035, "jitter": 0.5, "sat": 0.6}
        if self.te <= t < self.te + 0.12:
            p.update(tracking=0.5)
        if t >= self.tf:
            # paused-tape look: a noise bar parked across the picture
            p.update(tracking=0.25, jitter=0.9)
        return p


@functools.lru_cache(512)
def _osd_cached(lines):
    return cctv_osd(lines)


@functools.lru_cache(64)
def _tag_layer(x, y):
    L = TextLayer()
    L.rect([x, y, x + 66, y + 28], fill=(0, 0, 0, 200))
    L.text((x + 33, y + 14), "P-04", font("osd", 30), fill=(240, 240, 240), anchor="mm", shadow=False)
    return L


class Cell(Shot):
    """SLIDE 07: security camera, Incident 12. Time-lapse, then the hands."""

    def __init__(self, lapse=4.6, real=(9.0, 21.0), distort=3.6, post_hold=1.4):
        self.lapse, self.real, self.distort, self.post_hold = lapse, real, distort, post_hold
        self.t_real_end = lapse + real[1] - real[0]
        super().__init__(self.t_real_end + distort + post_hold)
        self.d = RENDERS / "cell"
        self.lapse_frames = list(range(1, 271, 6))

    def _src(self, t):
        if t < self.lapse:
            i = min(len(self.lapse_frames) - 1, int(t / self.lapse * len(self.lapse_frames)))
            f = self.lapse_frames[i]
            ft = (f - 1) / 30
            secs = 4 * 3600 * (t / self.lapse) + rng_dummy(i)
            return f, ft, secs
        ft = self.real[0] + min(t - self.lapse, self.real[1] - self.real[0])
        f = 1 + 2 * int(round(ft * 15))
        f = max(271, min(661, f + (0 if f % 2 else 1)))
        return f, ft, 4 * 3600 + 4 * 60 + 25 + (ft - self.real[0])

    def frame(self, t, rng):
        f, ft, secs = self._src(min(t, self.t_real_end))
        img = View(footage_frame(self.d / f"{f:04d}.png")).render()
        img = cctv_grade(barrel(img, 0.06), tint=(0.9, 1.0, 0.95))
        x = max(0.0, t - self.t_real_end)
        if x > 0:   # the recording distorts, then gives up
            k = min(1.0, x / 1.0)
            img = img * (1 - 0.5 * k) + cv2.GaussianBlur(img, (0, 0), 3) * 0.5 * k
            if t > self.t_real_end + self.distort:
                img = img * 0.0
        date = "11-14-1997" if secs < 3600 * 0.95 else "11-15-1997"
        lines = (
            (26, 22, "CAM 07", "la"), (W - 26, 22, date, "ra"),
            (W - 26, 50, clock(23, 2, 15, secs), "ra"), (26, H - 56, "SUBLEVEL 3 / OBS. C-12", "la"),
        ) + (((26, 50, ">> x240", "la"),) if t < self.lapse else ())
        if t <= self.t_real_end + self.distort:
            img = _osd_cached(lines).over(img)
        return img

    def fx(self, t):
        p = {"noise": 0.06, "streak": 0.03, "jitter": 0.5, "sat": 0.55}
        if t < self.lapse:
            p.update(jitter=0.9, tracking=0.15)
        x = t - self.t_real_end
        if 0 <= x < self.distort:
            k = min(1.0, x / 0.8)
            p.update(tracking=0.5 + 0.4 * k, tear=0.3 * k, rgb_split=3 * k, noise=0.06 + 0.1 * k, static=0.15 * k,
                     roll=1.0)
        elif x >= self.distort:
            p.update(static=0.0)
        return p


def rng_dummy(i):
    return (i * 7919) % 120


class EmptyCell(Shot):
    def __init__(self, dur):
        super().__init__(dur)

    def frame(self, t, rng):
        img = View(footage_frame(RENDERS / "stills" / "cell_empty.png")).render()
        img = cctv_grade(barrel(img, 0.06), tint=(0.9, 1.0, 0.95))
        lines = ((26, 22, "CAM 07", "la"), (W - 26, 22, "11-15-1997", "ra"),
                 (W - 26, 50, clock(7, 44, 2, t), "ra"), (26, H - 56, "SUBLEVEL 3 / OBS. C-12", "la"))
        return _osd_cached(lines).over(img)

    def fx(self, t):
        p = {"noise": 0.06, "streak": 0.03, "jitter": 0.5, "sat": 0.55}
        if t < 0.1:
            p.update(static=0.6, tracking=0.6)
        return p


# ------------------------------------------------------------------ slides with text
class Behaviors(Shot):
    ITEMS = ["VOCAL MIMICRY.", "FACIAL MIMICRY.", "MORPHOLOGICAL ALTERATION.", "PROLONGED OBSERVATION.",
             "PURSUIT.", "ATTACHMENT.", "DEPENDENCY.", "TERRITORIAL BEHAVIOR.", "AGGRESSIVE REACTION TO REJECTION."]

    def __init__(self, dur, t_items=1.0, step=0.85, t_fade=9.0, t_move=10.2, glitch=None, flash=None):
        super().__init__(dur)
        self.t_items, self.step, self.t_fade, self.t_move = t_items, step, t_fade, t_move
        self.glitch = glitch or []
        self.flash = flash
        self.chrome = look.slide_chrome(5, "BEHAVIOR")
        self.head = TextLayer().text((60, 84), "OBSERVED BEHAVIORS:", font("head", 30), fill=look.AMBER)
        f = font("monob", 21)
        self.rows = []
        for i, s in enumerate(self.ITEMS):
            L = TextLayer().text((84, 138 + i * 38), "—  " + s if i < 8 else "—  AGGRESSIVE REACTION TO",
                                 f, fill=look.WHITE)
            self.rows.append(L)
        x_rej = 84 + f.getlength("—  AGGRESSIVE REACTION TO ")
        self.rej_xy0 = (x_rej, 138 + 8 * 38)
        self.f_rej = f

    def frame(self, t, rng):
        img = look.slide_bg().copy()
        dim = 1 - look.ease((t - self.t_fade) / 1.0)
        img = self.chrome.over(img, 0.35 + 0.65 * dim)
        img = self.head.over(img, dim)
        for i, L in enumerate(self.rows):
            a = look.ease((t - (self.t_items + i * self.step)) / 0.25)
            img = L.over(img, a * dim)
        # REJECTION stays, then moves to the centre and grows
        if t >= self.t_items + 8 * self.step:
            m = look.ease((t - self.t_move) / 1.3)
            x0, y0 = self.rej_xy0
            size = int(21 + (54 - 21) * m)
            col = tuple(int(c0 + (c1 - c0) * m) for c0, c1 in zip(look.WHITE, (230, 60, 50)))
            x = x0 + (W / 2 - x0) * m
            y = y0 + 12 + (H / 2 - y0 - 12) * m
            L = _rej_layer(int(x), int(y), size, col, m > 0.02)
            img = L.over(img)
        if self.flash and any(a <= t < a + 1 / 30 + 0.001 for a in self.flash):
            img = Containment.grin_frame()
        return img

    def fx(self, t):
        for a, b in self.glitch:
            if a <= t < b:
                return {"tear": 0.8, "rgb_split": 6, "tracking": 0.7, "static": 0.25}
        return {}


@functools.lru_cache(256)
def _rej_layer(x, y, size, col, centered):
    L = TextLayer()
    L.text((x, y), "REJECTION.", font("monob", size), fill=col, anchor="mm" if centered else "lm")
    return L


def _grin():
    src = footage_frame(RENDERS / "containment" / "cam2" / "0673.png")
    return cctv_grade(View(src, (0.52, 0.47), 1.3).render())


Containment.grin_frame = staticmethod(functools.lru_cache(1)(_grin))


class Protocol(Shot):
    RULES = ["Do not remain alone with a specimen.",
             "Do not establish physical contact without authorization.",
             "Do not provide personal information.",
             "Do not mention family members, partners, or emotionally significant persons.",
             "Do not answer questions related to feelings.",
             "Do not accept gifts offered by the specimen.",
             "Do not promise to return.",
             'Do not say "I love you."']

    def __init__(self, dur, rule_times, t_black):
        super().__init__(dur)
        self.rule_times, self.t_black = rule_times, t_black
        self.chrome = look.slide_chrome(6, "INTERACTION PROTOCOL")
        self.head = TextLayer().text((56, 78), "PROTOCOL 04-B", font("head", 32), fill=look.AMBER)
        f = font("mono", 17)
        fb = font("monob", 17)
        self.rows = []
        y = 132
        for i, s in enumerate(self.RULES):
            L = TextLayer()
            L.text((56, y), f"{i + 1:02d}.", fb, fill=(150, 175, 200) if i < 7 else (230, 70, 60))
            lines = look.wrap(s, f if i < 7 else fb, 560)
            for j, ln in enumerate(lines):
                L.text((104, y + j * 25), ln, f if i < 7 else fb, fill=look.WHITE if i < 7 else (240, 90, 80))
            y += 25 * len(lines) + 15
            self.rows.append(L)

    def frame(self, t, rng):
        if t >= self.t_black:
            return look.blank()
        img = self.chrome.over(look.slide_bg())
        img = self.head.over(img, look.ease((t - 0.2) / 0.4))
        for L, tr in zip(self.rows, self.rule_times):
            img = L.over(img, look.ease((t - tr) / 0.6))
        return img

    def fx(self, t):
        if self.t_black <= t < self.t_black + 0.08:
            return {"static": 0.4}
        return {}


class Classification(Shot):
    def __init__(self, dur, events):
        """events: list of (t, row, text, mode) with mode in type|back|flash"""
        super().__init__(dur)
        self.events = events
        self.chrome = look.slide_chrome(9, "CLASSIFICATION")

    def state(self, t):
        rows = {}
        for (te, row, text, mode, speed) in self.events:
            if t < te:
                continue
            if mode == "type":
                n = min(len(text), int((t - te) / speed) + 1)
                rows[row] = text[:n]
            elif mode == "back":    # delete down to `text`
                cur = rows.get(row, "")
                n = max(len(text), len(cur) - int((t - te) / speed) - 1)
                rows[row] = cur[:n]
        return rows

    def frame(self, t, rng):
        img = self.chrome.over(look.slide_bg())
        rows = self.state(t)
        for row, s in rows.items():
            if not s:
                continue
            if row == 0:
                L = _term_line(row, s, "head", 64, look.WHITE)
            elif row == 9:   # AUTOMATIC CORRECTION banner, blinking
                if int(t * 3) % 2 == 0:
                    L = _term_line(row, s, "monob", 22, (255, 176, 40), box=True)
                else:
                    continue
            else:
                L = _term_line(row, s, "monob", 24, look.WHITE)
            flick = 1.0
            if row == 3 and any(a <= t < b for a, b in self.flicker):
                flick = 0.25 + 0.75 * (rng.random() > 0.5)
            img = L.over(img, flick)
        # cursor
        if int(t * 2.5) % 2 == 0:
            last = max(rows) if rows else 1
            if last != 9:
                s = rows.get(last, "")
                x, y, f = _row_geom(last, "monob" if last else "head", 24 if last else 64)
                cx = x + int(font("monob" if last else "head", 24 if last else 64).getlength(s)) + 4
                cv2.rectangle(img, (cx, y - 2), (cx + 12, y + (24 if last else 60)), (0.9, 0.9, 0.85), -1)
        return img

    flicker = []

    def fx(self, t):
        if any(a <= t < b for a, b in self.flicker):
            return {"tracking": 0.35, "jitter": 1.2}
        return {}


def _row_geom(row, f, size):
    y = {0: 110, 1: 210, 2: 252, 3: 330, 9: 400}[row]
    return 64, y, f


@functools.lru_cache(512)
def _term_line(row, s, f, size, col, box=False):
    L = TextLayer()
    x, y, _ = _row_geom(row, f, size)
    if box:
        w = font(f, size).getlength(s)
        L.rect([x - 10, y - 6, x + w + 10, y + size + 8], fill=(60, 30, 0, 230), outline=(255, 176, 40, 255), width=2)
    L.text((x, y), s, font(f, size), fill=col, shadow=not box)
    return L


class Hallway(Shot):
    """SLIDE 10: a home snapshot of someone familiar in a doorway. It does not stay familiar."""

    def __init__(self, dur, distort=(), flashes=(), clean=None, t_cut=None):
        super().__init__(dur)
        self.distort = distort        # [(t0, t1, strength)]
        self.flashes = flashes        # times of single-frame substitutions
        self.clean = clean            # (t0, t1) unnaturally clean & still
        self.t_cut = t_cut
        self.her = look.load(RENDERS / "stills" / "hallway_her.png")
        self.it = look.load(RENDERS / "stills" / "hallway_it.png")
        self.stamp = TextLayer()
        f = font("osd", 34)
        self.stamp.d.text((W - 120, H - 62), "'97 11 14", font=f, fill=(255, 140, 40, 255), anchor="mm")
        self.chrome = look.slide_chrome(10, "FINAL INSTRUCTION")

    def strength(self, t):
        s = 0.0
        for a, b, k in self.distort:
            if a <= t < b:
                s = max(s, k if not callable(k) else k(t))
        return s

    def frame(self, t, rng):
        if self.t_cut is not None and t >= self.t_cut:
            return look.blank()
        flash = any(a <= t < a + 1 / 30 + 0.001 for a in self.flashes)
        src = self.it if flash else self.her
        z = 1.0 + 0.35 * look.ease(t / self.dur)
        v = View(src, (0.5, 0.47), z)
        img = v.render()
        img = look.grade(img, contrast=1.1, sat=0.9, tint=(1.05, 0.98, 0.9))
        s = self.strength(t)
        if s > 0 and not flash:
            yy, xx = look._grid()
            amp = 14 * s
            mx = (xx / 2 + 0.5) * W + amp * np.sin(yy * 9 + t * 7)
            my = (yy / 2 + 0.5) * H + amp * 0.4 * np.sin(xx * 5 + t * 3)
            img = cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REFLECT)
        img = self.stamp.over(img)
        return self.chrome.over(img) if not flash else img

    def fx(self, t):
        if self.clean and self.clean[0] <= t < self.clean[1]:
            return {"noise": 0.004, "streak": 0.0, "jitter": 0.0, "wobble": 0.0, "dropout": 0.0, "head_switch": 0.3,
                    "chroma_noise": 0.0}
        s = self.strength(t)
        if s > 0:
            return {"tracking": 0.5 * s, "tear": 0.5 * s, "rgb_split": 5 * s, "static": 0.25 * s, "jitter": 0.4 + 2 * s,
                    "noise": 0.035 + 0.06 * s}
        return {}


class EndCards(Shot):
    def __init__(self, dur, t_end_text, t_corrupt, t_static, t_whisper_title, t_stop):
        super().__init__(dur)
        self.t = (t_end_text, t_corrupt, t_static, t_whisper_title, t_stop)
        self.end = TextLayer().text((W // 2, H // 2), "[END OF FILE B.C.]", font("monob", 28), anchor="mm")
        self.c1 = TextLayer().text((W // 2, 190), "FILE CORRUPTED", font("monob", 40), fill=(230, 60, 50), anchor="mm")
        self.c2 = TextLayer().text((W // 2, 262), "REASON:", font("mono", 22), fill=(200, 200, 195), anchor="mm")
        self.reason = '"THE DOCUMENT SHOULD NOT HAVE BEEN OPENED."'
        self.title = TextLayer().text((W // 2, H // 2), "DO YOU STILL LOVE ME?", font("osd", 44),
                                      fill=(225, 225, 225), anchor="mm")

    def frame(self, t, rng):
        te, tc, ts, tw, tstop = self.t
        img = look.blank()
        if te <= t < te + 3.2:
            img = self.end.over(img, env(t, te, te + 2.9, 0.3))
        if tc <= t < ts:
            img = self.c1.over(img)
            if t >= tc + 1.0:
                img = self.c2.over(img)
            if t >= tc + 2.0:
                n = min(len(self.reason), int((t - tc - 2.0) / 0.055) + 1)
                img = _reason_layer(self.reason[:n]).over(img)
            # corrupted blocks
            if rng.random() < 0.25:
                for _ in range(int(rng.integers(1, 5))):
                    x, y = int(rng.integers(0, W - 80)), int(rng.integers(0, H - 30))
                    w, h = int(rng.integers(20, 160)), int(rng.integers(4, 26))
                    img[y:y + h, x:x + w] = rng.random(3) * 0.8
        if tw <= t < tstop:
            img = self.title.over(img, env(t, tw + 0.6, tstop - 1.0, 0.6))
        if t >= tstop:
            img = look.blank((0.05, 0.12, 0.65))
        return img

    def fx(self, t):
        te, tc, ts, tw, tstop = self.t
        if tc <= t < ts:
            return {"tear": 0.35, "tracking": 0.3, "rgb_split": 2}
        if ts <= t < tw:
            k = min(1, (t - ts) / 0.6)
            return {"static": k, "tracking": 0.8}
        if t >= tstop:
            return {"noise": 0.01, "streak": 0.0, "head_switch": 0.0, "jitter": 0.0, "dropout": 0.0}
        return {}

    def post(self, img, t, rng):
        if t >= self.t[4]:
            img = _osd_icon("stop").over(vcr_osd(img, "STOP"))
        return img


@functools.lru_cache(64)
def _reason_layer(s):
    return TextLayer().text((W // 2, 312), s, font("monob", 21), fill=(235, 235, 230), anchor="mm")


class BondCard(Shot):
    """'BOND.' over the darkened forest photograph."""

    def __init__(self, dur, bg_shot):
        super().__init__(dur)
        self.bg = bg_shot
        self.L = TextLayer().text((W // 2, H // 2 - 6), "BOND.", font("head", 112), anchor="mm")

    def frame(self, t, rng):
        img = self.bg.frame(self.bg.dur, rng) * 0.25
        return self.L.over(img)

    def fx(self, t):
        return {"static": 0.3, "tracking": 0.4} if t < 0.07 else {}
