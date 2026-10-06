"""Procedural "photographs" of prehistoric cave paintings (SLIDE 02) and a medieval
manuscript illumination (SLIDE 03).

Every panel contains the same tall, thin figure — always beside a person.
Outputs build/stills/cave_*.png and build/stills/manuscript.png
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

from config import FONTS, STILLS

W, H = 1600, 1200
RNG = np.random.default_rng(40000)


# ----------------------------------------------------------------- noise
def fbm(h, w, octaves=7, base=4, seed=0, persistence=0.55):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.standard_normal((n + 3, int(n * w / h) + 3)).astype(np.float32)
        layer = ndimage.zoom(g, (h / n, w / n * (n / (int(n * w / h) or 1)) * (h / w) * (w / h)), order=3)
        layer = _fit(layer, h, w)
        out += amp * layer
        tot += amp
        amp *= persistence
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


def _fit(a, h, w):
    a = a[:h, :w]
    if a.shape != (h, w):
        a = np.pad(a, ((0, h - a.shape[0]), (0, w - a.shape[1])), mode="edge")
    return a


def shade(height, light=(-0.45, -0.4, 0.85), strength=250.0):
    gy, gx = np.gradient(height * strength)
    n = np.dstack([-gx, -gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    l = np.array(light, np.float32)
    l /= np.linalg.norm(l)
    return np.clip((n * l).sum(2), 0, 1)


# ----------------------------------------------------------------- drawing
def catmull(pts, closed=True, n=12):
    pts = list(pts)
    if closed:
        pts = [pts[-1]] + pts + pts[:2]
    else:
        pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (np.array(p, float) for p in pts[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(np.array(pts[-2], float))
    return [tuple(p) for p in out]


class Canvas:
    """A float mask (0..1) we draw pigment shapes into, in normalized panel coords."""

    def __init__(self, w=W, h=H, ss=2):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("L", (w * ss, h * ss), 0)
        self.d = ImageDraw.Draw(self.img)

    def tr(self, pts, box):
        x, y, s = box   # place shape: origin x,y (normalized), scale s (fraction of width); can mirror with s<0
        out = []
        for px, py in pts:
            X = (x + px * s) * self.w * self.ss
            Y = (y * self.h + py * abs(s) * self.w) * self.ss
            out.append((X, Y))
        return out

    def fill(self, pts, box, smooth=True, value=255):
        p = catmull(pts) if smooth else pts
        self.d.polygon(self.tr(p, box), fill=value)

    def stroke(self, pts, box, width, smooth=True, value=255):
        p = catmull(pts, closed=False) if smooth else pts
        P = self.tr(p, box)
        wpx = max(1, int(width * self.w * self.ss))
        self.d.line(P, fill=value, width=wpx, joint="curve")
        r = wpx / 2
        for X, Y in (P[0], P[-1]):
            self.d.ellipse([X - r, Y - r, X + r, Y + r], fill=value)

    def outline(self, pts, box, width, value=255):
        p = catmull(pts)
        self.stroke(p + [p[0]], box, width, smooth=False, value=value)

    def ellipse(self, cx, cy, rx, ry, box, value=255):
        x, y, s = box
        X, Y = (x + cx * s) * self.w * self.ss, (y * self.h + cy * abs(s) * self.w) * self.ss
        RX, RY = abs(rx * s) * self.w * self.ss, abs(ry * s) * self.w * self.ss
        self.d.ellipse([X - RX, Y - RY, X + RX, Y + RY], fill=value)

    def mask(self, blur=1.2):
        m = self.img.resize((self.w, self.h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))
        return np.asarray(m, np.float32) / 255.0


# ----------------------------------------------------------------- shapes (y down, ~unit width)
BISON = [(0.05, 0.30), (0.2, 0.17), (0.4, 0.1), (0.57, 0.03), (0.68, 0.08), (0.78, 0.17), (0.86, 0.22),
         (0.94, 0.36), (0.95, 0.45), (0.88, 0.5), (0.8, 0.56), (0.73, 0.52), (0.72, 0.63), (0.71, 0.76),
         (0.66, 0.76), (0.64, 0.6), (0.5, 0.56), (0.35, 0.56), (0.31, 0.64), (0.29, 0.77), (0.24, 0.77),
         (0.22, 0.6), (0.12, 0.52), (0.06, 0.43)]
BISON_HORN = [(0.82, 0.2), (0.85, 0.11), (0.82, 0.05)]
BISON_TAIL = [(0.06, 0.32), (0.0, 0.42), (0.01, 0.52)]
HORSE = [(0.1, 0.2), (0.35, 0.22), (0.55, 0.18), (0.68, 0.08), (0.75, 0.0), (0.8, 0.04), (0.85, 0.11),
         (0.95, 0.27), (0.92, 0.33), (0.82, 0.28), (0.72, 0.31), (0.66, 0.45), (0.67, 0.64), (0.68, 0.8),
         (0.63, 0.8), (0.6, 0.6), (0.45, 0.5), (0.3, 0.5), (0.25, 0.6), (0.22, 0.8), (0.17, 0.8),
         (0.16, 0.58), (0.08, 0.45), (0.06, 0.3)]
HORSE_TAIL = [(0.08, 0.22), (0.01, 0.35), (0.0, 0.55)]
HORSE_MANE = [(0.56, 0.16), (0.64, 0.07), (0.73, -0.02)]
DEER = [(0.12, 0.25), (0.4, 0.24), (0.55, 0.22), (0.62, 0.1), (0.66, 0.0), (0.72, -0.02), (0.8, 0.03),
        (0.78, 0.08), (0.7, 0.12), (0.66, 0.3), (0.62, 0.42), (0.63, 0.7), (0.6, 0.7), (0.56, 0.45),
        (0.4, 0.42), (0.28, 0.44), (0.25, 0.7), (0.22, 0.7), (0.2, 0.43), (0.1, 0.35)]
ANTLER_L = [(0.68, 0.0), (0.62, -0.12), (0.55, -0.2)]
ANTLER_L2 = [(0.63, -0.1), (0.68, -0.18)]
ANTLER_R = [(0.72, -0.01), (0.76, -0.14), (0.83, -0.2)]
ANTLER_R2 = [(0.76, -0.11), (0.71, -0.19)]
HAND = [(0.0, 0.62), (0.02, 0.42), (-0.02, 0.32), (-0.06, 0.2), (-0.03, 0.18), (0.04, 0.3), (0.06, 0.08),
        (0.1, 0.07), (0.11, 0.28), (0.13, 0.02), (0.17, 0.02), (0.17, 0.28), (0.2, 0.06), (0.24, 0.07),
        (0.22, 0.3), (0.27, 0.15), (0.3, 0.17), (0.26, 0.42), (0.24, 0.62)]


def person(cv, x, y, s, pose="stand", w=0.012, spear=False, bow=False):
    """Stick figure ~0.1*s tall. (x, y) = feet centre."""
    b = (x, y, s)
    head = (0, -1.0)
    if pose == "stand":
        cv.ellipse(0, -0.9, 0.06, 0.07, b)
        cv.stroke([(0, -0.82), (0.0, -0.45)], b, w)
        cv.stroke([(-0.18, -0.7), (0, -0.74), (0.2, -0.62)], b, w)
        cv.stroke([(-0.14, 0), (0, -0.45), (0.14, 0)], b, w, smooth=False)
        if spear:
            cv.stroke([(0.1, -0.35), (0.42, -1.25)], b, w * 0.6, smooth=False)
        if bow:
            cv.stroke([(0.26, -0.95), (0.36, -0.68), (0.26, -0.4)], b, w * 0.6)
    elif pose == "run":
        cv.ellipse(0.06, -0.9, 0.06, 0.07, b)
        cv.stroke([(0.05, -0.82), (-0.02, -0.45)], b, w)
        cv.stroke([(-0.25, -0.66), (0.02, -0.72), (0.3, -0.8)], b, w)
        cv.stroke([(-0.3, -0.05), (-0.02, -0.45), (0.22, -0.2), (0.3, 0)], b, w, smooth=False)
        if spear:
            cv.stroke([(-0.1, -0.6), (0.7, -1.1)], b, w * 0.6, smooth=False)
    elif pose == "sit":
        cv.ellipse(0, -0.62, 0.06, 0.07, b)
        cv.stroke([(0, -0.55), (0.02, -0.2)], b, w)
        cv.stroke([(0.02, -0.2), (0.25, -0.22), (0.3, 0)], b, w, smooth=False)
        cv.stroke([(0, -0.45), (0.2, -0.35)], b, w)
    elif pose == "kneel":
        cv.ellipse(0.1, -0.68, 0.06, 0.07, b)
        cv.stroke([(0.08, -0.6), (0.0, -0.3)], b, w)
        cv.stroke([(0.0, -0.3), (0.0, 0.0), (-0.25, 0.0)], b, w, smooth=False)
        cv.stroke([(0.06, -0.5), (0.28, -0.62), (0.36, -0.75)], b, w)
        cv.stroke([(0.06, -0.5), (0.26, -0.5), (0.36, -0.6)], b, w)
    return head


def tall_one(cv, x, y, s, w=0.011, arm=None, lean=0.0, sitting=False):
    """The recurring figure: much taller than people, featureless oval head,
    arms hanging to the knees. arm='embrace' wraps a long arm around a person to the right."""
    b = (x, y, s)
    if sitting:
        cv.ellipse(0.02, -1.05, 0.05, 0.085, b)
        cv.stroke([(0.02, -0.95), (0.0, -0.75), (0.0, -0.3)], b, w)
        cv.stroke([(0.0, -0.3), (0.32, -0.32), (0.36, 0.0)], b, w, smooth=False)
        cv.stroke([(0.0, -0.75), (0.18, -0.6), (0.4, -0.55), (0.58, -0.5)], b, w * 0.8)
        cv.stroke([(0.0, -0.75), (-0.1, -0.45), (-0.08, -0.2)], b, w * 0.8)
        return
    cv.ellipse(lean * 0.3, -1.62, 0.055, 0.1, b)
    cv.stroke([(lean * 0.25, -1.5), (lean * 0.12, -1.25), (0.0, -0.7)], b, w)
    cv.stroke([(-0.1, 0), (-0.03, -0.38), (0.0, -0.7), (0.04, -0.38), (0.12, 0)], b, w)
    if arm == "embrace":
        cv.stroke([(lean * 0.15, -1.3), (0.22, -1.2), (0.42, -0.95), (0.44, -0.66), (0.3, -0.56), (0.18, -0.6)],
                  b, w * 0.8)
        cv.stroke([(lean * 0.15, -1.3), (0.1, -1.0), (0.22, -0.72), (0.38, -0.62), (0.46, -0.62)], b, w * 0.8)
    elif arm == "reach":
        cv.stroke([(lean * 0.15, -1.3), (0.3, -1.15), (0.6, -1.0), (0.78, -0.95)], b, w * 0.8)
        cv.stroke([(lean * 0.15, -1.3), (-0.12, -0.95), (-0.14, -0.5)], b, w * 0.8)
    elif arm == "hand":
        cv.stroke([(lean * 0.15, -1.3), (0.15, -0.95), (0.3, -0.62)], b, w * 0.8)
        cv.stroke([(lean * 0.15, -1.3), (-0.13, -0.95), (-0.15, -0.5)], b, w * 0.8)
    else:
        cv.stroke([(lean * 0.15, -1.3), (0.12, -0.95), (0.14, -0.45)], b, w * 0.8)
        cv.stroke([(lean * 0.15, -1.3), (-0.12, -0.95), (-0.14, -0.45)], b, w * 0.8)


def fire(cv, x, y, s):
    b = (x, y, s)
    for i, (dx, hgt) in enumerate([(-0.06, 0.25), (0.0, 0.38), (0.07, 0.28), (-0.02, 0.2), (0.04, 0.33)]):
        cv.fill([(dx - 0.05, 0), (dx - 0.02, -hgt * 0.5), (dx + 0.01, -hgt), (dx + 0.03, -hgt * 0.45),
                 (dx + 0.05, 0)], b)


# ----------------------------------------------------------------- rock + pigment
def rock(seed, tone=(0.70, 0.56, 0.42)):
    h1 = fbm(H, W, 8, 3, seed)
    h2 = fbm(H, W, 7, 12, seed + 1, persistence=0.62)
    grit = RNG.standard_normal((H, W)).astype(np.float32)
    grit = ndimage.gaussian_filter(grit, 0.8)
    ridge = 1 - np.abs(fbm(H, W, 6, 4, seed + 4) - 0.5) * 2          # ridged noise: folds and ledges
    height = 0.55 * h1 + 0.25 * h2 + 0.2 * ridge ** 3 + 0.0025 * grit
    cracks = np.abs(fbm(H, W, 5, 5, seed + 2) - 0.5) < 0.004
    height = height - ndimage.gaussian_filter(cracks.astype(np.float32), 1.2) * 0.03
    lit = shade(height, strength=120.0)
    calc = np.clip((fbm(H, W, 6, 6, seed + 3) - 0.55) * 3, 0, 1)        # pale calcite veils
    speck = np.clip(ndimage.gaussian_filter(RNG.standard_normal((H, W)).astype(np.float32), 1.0) * 0.6, -0.5, 0.5)
    base = np.array(tone, np.float32)[None, None] * (0.62 + 0.55 * h2[..., None] + 0.12 * speck[..., None])
    base = base * (1 - 0.35 * calc[..., None]) + 0.85 * calc[..., None] * 0.35
    return base, height, lit


def warp(mask, seed, amp=5.0):
    """Hand-painted, irregular edges: displace the mask by a smooth noise field."""
    dx = (fbm(H, W, 4, 24, seed + 11) - 0.5) * 2 * amp
    dy = (fbm(H, W, 4, 24, seed + 12) - 0.5) * 2 * amp
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return ndimage.map_coordinates(mask, [yy + dy, xx + dx], order=1, mode="nearest")


def apply_pigment(rgb, mask, color, seed, density=0.85, flake=0.35):
    mask = warp(mask, seed)
    grain = fbm(H, W, 6, 40, seed)
    absorb = np.clip(0.3 + 0.95 * grain, 0, 1)
    flakes = (fbm(H, W, 5, 18, seed + 7) > (1 - flake * 0.5)).astype(np.float32)
    flakes = ndimage.gaussian_filter(flakes, 1.2)
    m = np.clip(mask * absorb * density * (1 - flakes * 0.85), 0, 1)[..., None]
    col = np.array(color, np.float32)[None, None]
    return rgb * (1 - m) + (rgb * col * 1.6) * m * 0.45 + col * m * 0.55


def light_and_photo(rgb, lit, torch=(0.25, 0.85), warm=True, seed=0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.hypot((xx / W - torch[0]) * 1.2, yy / H - torch[1])
    falloff = np.clip(1.25 - d * 1.05, 0.08, 1.0) ** 1.6
    img = rgb * (0.45 + 0.75 * lit[..., None]) * falloff[..., None]
    if warm:
        img *= np.array([1.08, 0.96, 0.82], np.float32)
    img = np.clip(img, 0, 1)
    # photographic: slight vignette + grain
    vig = 1 - 0.35 * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2.2)
    img *= vig[..., None]
    img += RNG.normal(0, 0.025, img.shape).astype(np.float32)
    return np.clip(img, 0, 1)


def save(img, name):
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(STILLS / name)
    print("wrote", name)


RED = (0.62, 0.16, 0.08)
BLACK = (0.08, 0.06, 0.05)
OCHRE = (0.78, 0.52, 0.18)
WHITE = (0.93, 0.9, 0.82)


def panel_hunt():
    rgb, height, lit = rock(11)
    red, black, white = Canvas(), Canvas(), Canvas()
    red.fill(BISON, (0.08, 0.22, 0.30))
    black.outline(BISON, (0.08, 0.22, 0.30), 0.006)
    black.stroke(BISON_HORN, (0.08, 0.22, 0.30), 0.006)
    black.stroke(BISON_TAIL, (0.08, 0.22, 0.30), 0.004)
    for (x, y, s) in [(0.5, 0.18, -0.2), (0.62, 0.3, -0.17)]:
        black.fill(HORSE, (x + 0.2, y, s))
        black.stroke(HORSE_TAIL, (x + 0.2, y, s), 0.006)
    red.fill(DEER, (0.36, 0.5, 0.16))
    for (a, bb) in [(ANTLER_L, ANTLER_L2), (ANTLER_R, ANTLER_R2)]:
        red.stroke(a, (0.36, 0.5, 0.16), 0.004)
        red.stroke(bb, (0.36, 0.5, 0.16), 0.003)
    for i, x in enumerate([0.12, 0.2, 0.28]):
        person(black, x, 0.83, 0.1, "run", spear=True)
    person(black, 0.62, 0.84, 0.1, "stand", bow=True)
    tall_one(white, 0.71, 0.86, 0.105, arm="hand")
    person(black, 0.75, 0.86, 0.1, "stand")
    rgb = apply_pigment(rgb, red.mask(), RED, 101)
    rgb = apply_pigment(rgb, black.mask(), BLACK, 102, density=1.0, flake=0.2)
    rgb = apply_pigment(rgb, white.mask(), WHITE, 103, density=1.0, flake=0.2)
    save(light_and_photo(rgb, lit, torch=(0.4, 0.7)), "cave_hunt.png")


def panel_fire():
    rgb, height, lit = rock(21, tone=(0.66, 0.52, 0.4))
    red, black, white, ochre = Canvas(), Canvas(), Canvas(), Canvas()
    fire(red, 0.5, 0.66, 0.35)
    fire(ochre, 0.5, 0.66, 0.2)
    for x, flip in [(0.3, 1), (0.37, 1), (0.63, -1), (0.7, -1)]:
        person(black, x, 0.7, 0.13 * flip, "sit")
    person(black, 0.42, 0.82, 0.13, "sit")
    tall_one(white, 0.56, 0.84, 0.11, sitting=True)
    for x in [0.12, 0.2, 0.84]:
        black.fill(BISON, (x - 0.05, 0.12 + 0.05 * (x > 0.5), 0.1 * (1 if x < 0.5 else -1)))
    rgb = apply_pigment(rgb, ochre.mask(), OCHRE, 201)
    rgb = apply_pigment(rgb, red.mask(), RED, 202)
    rgb = apply_pigment(rgb, black.mask(), BLACK, 203, density=1.0, flake=0.2)
    rgb = apply_pigment(rgb, white.mask(), WHITE, 204, density=1.0, flake=0.2)
    save(light_and_photo(rgb, lit, torch=(0.5, 0.75)), "cave_fire.png")


def panel_hands():
    rgb, height, lit = rock(31, tone=(0.68, 0.55, 0.43))
    spray, black, white = Canvas(), Canvas(), Canvas()
    holes = Canvas()
    for i, (x, y, s, rot) in enumerate([(0.1, 0.12, 0.13, 0), (0.24, 0.08, 0.12, 0), (0.36, 0.16, -0.13, 0),
                                        (0.72, 0.1, 0.12, 0), (0.84, 0.14, -0.12, 0), (0.6, 0.12, 0.11, 0)]):
        spray.ellipse(0.12, 0.33, 0.33, 0.42, (x, y, s))
        holes.fill(HAND, (x, y, s), smooth=False)
    m = np.clip(spray.mask(18) * 1.3 - holes.mask(1.0) * 1.3, 0, 1)
    tall_one(white, 0.5, 0.92, 0.17, arm="hand")
    person(black, 0.56, 0.92, 0.12, "stand")
    rgb = apply_pigment(rgb, m, RED, 301, density=0.75, flake=0.15)
    rgb = apply_pigment(rgb, black.mask(), BLACK, 302, density=1.0, flake=0.2)
    rgb = apply_pigment(rgb, white.mask(), WHITE, 303, density=1.0, flake=0.2)
    save(light_and_photo(rgb, lit, torch=(0.55, 0.6)), "cave_hands.png")


def panel_embrace():
    rgb, height, lit = rock(41, tone=(0.72, 0.58, 0.45))
    white, black = Canvas(), Canvas()
    tall_one(white, 0.38, 0.95, 0.42, w=0.009, arm="embrace", lean=0.35)
    person(black, 0.52, 0.95, 0.3, "stand", w=0.009)
    rgb = apply_pigment(rgb, black.mask(), BLACK, 401, density=1.0, flake=0.2)
    rgb = apply_pigment(rgb, white.mask(), WHITE, 402, density=1.0, flake=0.2)
    save(light_and_photo(rgb, lit, torch=(0.45, 0.55)), "cave_embrace.png")


def panel_kneel():
    rgb, height, lit = rock(51, tone=(0.64, 0.5, 0.38))
    white, black, red = Canvas(), Canvas(), Canvas()
    tall_one(white, 0.6, 0.93, 0.36, w=0.009, arm="reach", lean=-0.1)
    person(black, 0.36, 0.93, 0.25, "kneel", w=0.01)
    for i in range(7):   # dots between them
        red.ellipse(0.0, 0.0, 0.006, 0.006, (0.42 + i * 0.022, 0.62 - 0.012 * math.sin(i), 1.0))
    rgb = apply_pigment(rgb, red.mask(), RED, 501)
    rgb = apply_pigment(rgb, black.mask(), BLACK, 502, density=1.0, flake=0.2)
    rgb = apply_pigment(rgb, white.mask(), WHITE, 503, density=1.0, flake=0.2)
    save(light_and_photo(rgb, lit, torch=(0.5, 0.65)), "cave_kneel.png")


# ----------------------------------------------------------------- manuscript
def manuscript():
    rng = np.random.default_rng(1347)
    parch = np.array([0.86, 0.78, 0.6], np.float32)[None, None] * (0.86 + 0.18 * fbm(H, W, 7, 3, 70)[..., None])
    stains = np.clip((fbm(H, W, 6, 2, 71) - 0.6) * 2.5, 0, 1)[..., None]
    parch = parch * (1 - 0.35 * stains * np.array([0.6, 0.8, 1.0]))
    img = Image.fromarray((np.clip(parch, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # border
    d.rectangle([90, 70, W - 90, H - 70], outline=(110, 30, 25), width=10)
    d.rectangle([112, 92, W - 112, H - 92], outline=(160, 120, 40), width=4)
    # illustration frame with gold ground
    fx0, fy0, fx1, fy1 = 300, 150, W - 300, 840
    gold = fbm(fy1 - fy0, fx1 - fx0, 5, 8, 72)
    ga = np.dstack([0.78 + 0.2 * gold, 0.6 + 0.16 * gold, 0.22 + 0.1 * gold])
    gimg = Image.fromarray((np.clip(ga, 0, 1) * 255).astype(np.uint8))
    gd = ImageDraw.Draw(gimg)
    for y in range(0, fy1 - fy0, 36):     # punched diaper pattern
        for x in range(0, fx1 - fx0, 36):
            gd.polygon([(x + 18, y + 4), (x + 32, y + 18), (x + 18, y + 32), (x + 4, y + 18)],
                       outline=(150, 105, 30))
    img.paste(gimg, (fx0, fy0))
    d.rectangle([fx0, fy0, fx1, fy1], outline=(40, 30, 60), width=8)
    d.rectangle([fx0 - 14, fy0 - 14, fx1 + 14, fy1 + 14], outline=(30, 60, 140), width=8)
    # ground
    d.polygon([(fx0, fy1 - 120), (fx1, fy1 - 150), (fx1, fy1), (fx0, fy1)], fill=(70, 90, 50))

    def figure(cx, foot, h, robe, mantle, skin=(222, 190, 160), tall=False):
        hw = h * 0.16
        body = [(cx - hw * 0.55, foot - h * 0.78), (cx + hw * 0.55, foot - h * 0.78), (cx + hw * 1.05, foot),
                (cx - hw * 1.05, foot)]
        d.polygon(body, fill=robe, outline=(30, 20, 20))
        d.polygon([(cx - hw * 0.55, foot - h * 0.78), (cx + hw * 0.2, foot - h * 0.78),
                   (cx + hw * 0.4, foot - h * 0.3), (cx - hw * 0.9, foot - h * 0.1)], fill=mantle, outline=(30, 20, 20))
        for k in range(3):   # drapery folds
            xx = cx - hw * 0.6 + k * hw * 0.55
            d.line([(xx, foot - h * 0.6), (xx + hw * 0.15 * (k - 1), foot - 4)], fill=(30, 20, 20), width=3)
        hr = h * (0.075 if not tall else 0.06)
        hy = foot - h * 0.78 - hr * 1.1
        d.ellipse([cx - hr, hy - hr * 1.2, cx + hr, hy + hr * 1.2 if tall else hy + hr], fill=skin, outline=(40, 25, 20), width=3)
        return (cx, hy, hr)

    figs = []
    figs.append(figure(470, 760, 420, (150, 30, 30), (40, 60, 140)))
    figs.append(figure(610, 770, 400, (40, 70, 130), (170, 140, 60)))
    pas = figure(780, 775, 560, (232, 226, 210), (210, 205, 190), skin=(236, 230, 214), tall=True)
    figs.append(figure(930, 770, 410, (120, 40, 70), (40, 100, 70)))
    figs.append(figure(1080, 765, 390, (40, 60, 140), (150, 30, 30)))
    # faces for the ordinary figures
    for (cx, hy, hr) in figs:
        d.arc([cx - hr * 0.5, hy - hr * 0.3, cx - hr * 0.1, hy], 200, 340, fill=(40, 25, 20), width=3)
        d.arc([cx + hr * 0.1, hy - hr * 0.3, cx + hr * 0.5, hy], 200, 340, fill=(40, 25, 20), width=3)
        d.line([(cx, hy - hr * 0.1), (cx - hr * 0.1, hy + hr * 0.3)], fill=(90, 50, 40), width=3)
        d.line([(cx - hr * 0.25, hy + hr * 0.55), (cx + hr * 0.25, hy + hr * 0.55)], fill=(140, 50, 40), width=3)
    # long pale arms of the tall one around its neighbour
    cx, hy, hr = pas
    d.line([(cx + 30, hy + 120), (cx + 110, hy + 160), (cx + 180, hy + 230), (cx + 200, hy + 300)],
           fill=(236, 230, 214), width=16, joint="curve")
    d.line([(cx + 30, hy + 120), (cx + 110, hy + 160), (cx + 180, hy + 230), (cx + 200, hy + 300)],
           fill=(40, 25, 20), width=2, joint="curve")
    # its face has been scratched out of the vellum, as with defaced demons in real codices
    sc = Image.new("L", img.size, 0)
    sd = ImageDraw.Draw(sc)
    for k in range(140):
        x0 = cx + rng.uniform(-hr * 1.3, hr * 1.3)
        y0 = hy + rng.uniform(-hr * 1.5, hr * 1.4)
        ang = rng.uniform(-0.6, 0.6) + (math.pi / 4 if k % 2 else -math.pi / 4)
        ln = rng.uniform(10, 40)
        sd.line([(x0, y0), (x0 + ln * math.cos(ang), y0 + ln * math.sin(ang))], fill=255, width=int(rng.uniform(2, 5)))
    scm = np.asarray(sc.filter(ImageFilter.GaussianBlur(1.0)), np.float32)[..., None] / 255
    arr = np.asarray(img, np.float32) / 255
    raw = np.array([0.55, 0.42, 0.28])[None, None] * (0.7 + 0.5 * fbm(H, W, 5, 30, 73)[..., None])
    arr = arr * (1 - scm) + raw * scm
    img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # text block in blackletter, with a red initial
    f = ImageFont.truetype(str(FONTS / "UnifrakturMaguntia-Book.ttf"), 46)
    fi = ImageFont.truetype(str(FONTS / "UnifrakturMaguntia-Book.ttf"), 130)
    lines = ["et vidi inter eos alteram quae non erat ex eis",
             "et faciem eius nemo recordabatur nec nomen",
             "sed amabat eos et numquam sola erat"]
    d.text((300, 880), "E", font=fi, fill=(170, 30, 25))
    for i, t in enumerate(lines):
        d.text((400 if i == 0 else 300, 905 + i * 62), t, font=f, fill=(35, 25, 20))
    arr = np.asarray(img, np.float32) / 255
    arr = arr * (0.9 + 0.1 * fbm(H, W, 6, 50, 74)[..., None])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1 - 0.45 * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2.0)
    arr = arr * vig[..., None] + RNG.normal(0, 0.02, arr.shape)
    save(arr, "manuscript.png")
    return pas


if __name__ == "__main__":
    panel_hunt()
    panel_fire()
    panel_hands()
    panel_embrace()
    panel_kneel()
    manuscript()
