"""Visual building blocks shared by every shot: fonts, text, photo framing
(Ken Burns with box tracking), censor bars, the training-slide template."""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import FONTS, H, W

# ------------------------------------------------------------------ palette
NAVY_TOP = np.array([0.05, 0.10, 0.20], np.float32)
NAVY_BOT = np.array([0.01, 0.03, 0.08], np.float32)
WHITE = (236, 238, 232)
AMBER = (255, 176, 40)
RED = (220, 40, 30)
CYAN = (150, 220, 230)


@functools.lru_cache(None)
def font(name, size):
    files = {"head": "IBMPlexSansCondensed-Bold.ttf", "headm": "IBMPlexSansCondensed-Medium.ttf",
             "body": "IBMPlexSansCondensed-Regular.ttf", "mono": "IBMPlexMono-Regular.ttf",
             "monob": "IBMPlexMono-Bold.ttf", "osd": "VT323-Regular.ttf", "type": "CourierPrime-Regular.ttf",
             "typeb": "CourierPrime-Bold.ttf", "elite": "SpecialElite-Regular.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), size)


def to_f(img):
    return np.asarray(img, np.float32) / 255.0


def to_u8(a):
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def blank(color=(0, 0, 0)):
    a = np.empty((H, W, 3), np.float32)
    a[:] = np.array(color, np.float32)
    return a


# ------------------------------------------------------------------ text
class TextLayer:
    """RGBA text drawn once and composited many times (alpha can be animated)."""

    def __init__(self):
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self._arr = None

    def text(self, xy, s, f, fill=WHITE, anchor="la", spacing=4, shadow=True):
        if shadow:
            self.d.text((xy[0] + 2, xy[1] + 2), s, font=f, fill=(0, 0, 0, 200), anchor=anchor, spacing=spacing)
        self.d.text(xy, s, font=f, fill=fill + (255,) if len(fill) == 3 else fill, anchor=anchor, spacing=spacing)
        self._arr = None
        return self

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(box, fill=fill, outline=outline, width=width)
        self._arr = None
        return self

    def line(self, pts, fill, width=1):
        self.d.line(pts, fill=fill, width=width)
        self._arr = None
        return self

    @property
    def arr(self):
        if self._arr is None:
            a = np.asarray(self.img, np.float32) / 255.0
            self._arr = (a[..., :3], a[..., 3:4])
        return self._arr

    def over(self, base, alpha=1.0):
        rgb, a = self.arr
        a = a * alpha
        return base * (1 - a) + rgb * a


def wrap(s, f, width):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if f.getlength(t) > width and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ photos
@functools.lru_cache(64)
def load(path, mode="rgb"):
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    if mode == "sepia":
        g = im @ np.array([0.299, 0.587, 0.114], np.float32)
        im = np.clip(g[..., None] * np.array([1.07, 0.95, 0.76], np.float32) + 0.02, 0, 1)
    elif mode == "gray":
        g = im @ np.array([0.299, 0.587, 0.114], np.float32)
        im = np.repeat(g[..., None], 3, axis=2)
    return np.ascontiguousarray(im)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class View:
    """Places a source image in the frame: `center` (normalized source coords) shown at
    the frame centre with `zoom` (1 = cover the frame)."""

    def __init__(self, src, center=(0.5, 0.5), zoom=1.0, rot=0.0):
        self.src = src
        sh, sw = src.shape[:2]
        cover = max(W / sw, H / sh)
        self.s = cover * zoom
        self.cx, self.cy = center[0] * sw, center[1] * sh
        self.rot = rot
        self.sw, self.sh = sw, sh
        a = math.radians(rot)
        c, s_ = math.cos(a) * self.s, math.sin(a) * self.s
        self.M = np.array([[c, -s_, W / 2 - c * self.cx + s_ * self.cy],
                           [s_, c, H / 2 - s_ * self.cx - c * self.cy]], np.float32)

    def render(self, border=0.0):
        return cv2.warpAffine(self.src, self.M, (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(border, border, border))

    def box(self, b):
        """normalized source box -> frame pixel box"""
        pts = np.array([[b[0] * self.sw, b[1] * self.sh, 1], [b[2] * self.sw, b[1] * self.sh, 1],
                        [b[0] * self.sw, b[3] * self.sh, 1], [b[2] * self.sw, b[3] * self.sh, 1]], np.float32)
        p = pts @ self.M.T
        return [p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()]


def kenburns(src, t, dur, c0=(0.5, 0.5), c1=(0.5, 0.5), z0=1.0, z1=1.08, smooth=True):
    x = ease(t / dur) if smooth else min(max(t / dur, 0), 1)
    c = (c0[0] + (c1[0] - c0[0]) * x, c0[1] + (c1[1] - c0[1]) * x)
    return View(src, c, z0 + (z1 - z0) * x)


def censor(img, box, pad=0.18, jitter=0.0, rng=None, color=0.0):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    x0 -= w * pad
    x1 += w * pad
    y0 -= h * pad * 0.8
    y1 += h * pad * 0.8
    if jitter and rng is not None:
        j = rng.normal(0, jitter, 4)
        x0, y0, x1, y1 = x0 + j[0], y0 + j[1], x1 + j[2], y1 + j[3]
    x0, y0 = int(max(0, x0)), int(max(0, y0))
    x1, y1 = int(min(W, x1)), int(min(H, y1))
    if x1 > x0 and y1 > y0:
        img[y0:y1, x0:x1] = color
    return img


def pixelate(img, box, block=10, pad=0.2):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    x0, x1 = int(max(0, x0 - w * pad)), int(min(W, x1 + w * pad))
    y0, y1 = int(max(0, y0 - h * pad)), int(min(H, y1 + h * pad))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return img
    roi = img[y0:y1, x0:x1]
    small = cv2.resize(roi, (max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)), interpolation=cv2.INTER_AREA)
    img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    return img


def grade(img, contrast=1.0, bright=0.0, sat=1.0, tint=(1, 1, 1), gamma=1.0):
    g = img @ np.array([0.299, 0.587, 0.114], np.float32)
    img = g[..., None] + (img - g[..., None]) * sat
    img = (img - 0.5) * contrast + 0.5 + bright
    img = np.clip(img, 0, 1) ** gamma
    return np.clip(img * np.array(tint, np.float32), 0, 1)


def vignette(img, k=0.4):
    yy, xx = _grid()
    return img * (1 - k * (xx ** 2 + yy ** 2))[..., None]


@functools.lru_cache(1)
def _grid():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return (yy / H - 0.5) * 2, (xx / W - 0.5) * 2


def film_damage(img, rng, amount=1.0):
    """Dust specks and hairline scratches for archival photographs."""
    n = int(rng.poisson(6 * amount))
    for _ in range(n):
        x, y = rng.integers(0, W), rng.integers(0, H)
        r = rng.integers(1, 3)
        v = 0.9 if rng.random() < 0.5 else 0.05
        cv2.circle(img, (int(x), int(y)), int(r), (v, v, v), -1)
    if rng.random() < 0.35 * amount:
        x = int(rng.integers(0, W))
        cv2.line(img, (x, 0), (x + int(rng.integers(-20, 20)), H), (0.85, 0.85, 0.82), 1)
    return img


# ------------------------------------------------------------------ slide template
@functools.lru_cache(1)
def slide_bg():
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg = NAVY_TOP * (1 - yy) + NAVY_BOT * yy
    bg = np.repeat(bg, W, axis=1)
    rows = (np.arange(H) % 3 == 0).astype(np.float32)[:, None, None]
    bg = bg * (1 - 0.12 * rows)
    return np.ascontiguousarray(bg)


def emblem(layer, cx, cy, r, color=(200, 210, 220)):
    d = layer.d
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (255,), width=3)
    d.ellipse([cx - r * 0.82, cy - r * 0.82, cx + r * 0.82, cy + r * 0.82], outline=color + (255,), width=1)
    # an open eye inside a triangle: watched, never alone
    tri = [(cx, cy - r * 0.6), (cx + r * 0.55, cy + r * 0.38), (cx - r * 0.55, cy + r * 0.38)]
    d.polygon(tri, outline=color + (255,), width=2)
    d.ellipse([cx - r * 0.24, cy - r * 0.1, cx + r * 0.24, cy + r * 0.2], outline=color + (255,), width=2)
    d.ellipse([cx - r * 0.08, cy - r * 0.02, cx + r * 0.08, cy + r * 0.12], fill=color + (255,))
    f = font("monob", max(8, int(r * 0.2)))
    d.text((cx, cy + r * 0.62), "B.C.", font=f, fill=color + (255,), anchor="mm")
    return layer


def slide_chrome(slide_no, title):
    """Header bar + footer used on content slides."""
    L = TextLayer()
    L.rect([0, 0, W, 46], fill=(8, 16, 34, 235))
    L.rect([0, 46, W, 48], fill=(120, 150, 180, 255))
    L.text((22, 23), f"SLIDE {slide_no:02d}", font("monob", 17), fill=(150, 175, 200), anchor="lm", shadow=False)
    L.text((128, 23), title, font("head", 24), fill=WHITE, anchor="lm", shadow=False)
    emblem(L, W - 30, 23, 17)
    L.rect([0, H - 30, W, H], fill=(8, 16, 34, 235))
    L.text((22, H - 15), "TAPE B.C.  //  INSTRUCTIONAL MATERIAL  //  ACCESS LEVEL B.C.", font("mono", 12),
           fill=(130, 150, 170), anchor="lm", shadow=False)
    L.text((W - 22, H - 15), "RESTRICTED", font("monob", 12), fill=(200, 70, 60), anchor="rm", shadow=False)
    return L
