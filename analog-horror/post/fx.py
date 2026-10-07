"""CCTV -> VHS image degradation primitives (numpy / OpenCV, float32 RGB in [0,1])."""
import math
import numpy as np
import cv2

OUT_W, OUT_H = 1440, 1080          # 4:3 master
CCTV_W, CCTV_H = 704, 528          # effective camera/DVR resolution


def to_float(img_bgr_u8):
    return cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


_maps = {}


def barrel(img, k1=-0.055, k2=0.0):
    h, w = img.shape[:2]
    key = (h, w, k1, k2)
    if key not in _maps:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        nx, ny = (x - w / 2) / (w / 2), (y - h / 2) / (w / 2)
        r2 = nx * nx + ny * ny
        f = 1 + k1 * r2 + k2 * r2 * r2
        f = f / (1 + k1 * 0.5)       # keep the center scale ~1
        _maps[key] = ((nx * f) * (w / 2) + w / 2, (ny * f) * (w / 2) + h / 2)
    mx, my = _maps[key]
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def vignette(img, strength=0.35):
    h, w = img.shape[:2]
    key = ("v", h, w, strength)
    if key not in _maps:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2)) / math.sqrt(2)
        _maps[key] = (1 - strength * r ** 2.2)[..., None]
    return img * _maps[key]


def grade_cctv(img):
    """Tungsten interior seen by a cheap CCTV with fluorescent white balance + AGC."""
    img = img * np.array([0.86, 1.0, 0.88], np.float32)
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    img = luma[..., None] + (img - luma[..., None]) * 0.58          # desaturate
    img = img * 1.18
    img = 0.035 + (1 - 0.035) * np.clip(img, 0, 1.4) ** 0.88          # AGC lifts the floor
    img = img + np.array([-0.004, 0.008, -0.002], np.float32) * (1 - luma[..., None])
    return img


def bloom(img, thresh=0.72, sigma=10.0, amount=0.55):
    b = np.clip(img - thresh, 0, None)
    b = cv2.GaussianBlur(b, (0, 0), sigma)
    return img + amount * b


def unsharp(img, sigma=1.0, amount=0.7):
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return img + amount * (img - blur)


def ycc(img):
    y = img @ np.array([0.299, 0.587, 0.114], np.float32)
    cb = (img[..., 2] - y) * 0.564
    cr = (img[..., 0] - y) * 0.713
    return y, cb, cr


def rgb(y, cb, cr):
    r = y + 1.403 * cr
    b = y + 1.773 * cb
    g = (y - 0.299 * r - 0.114 * b) / 0.587
    return np.stack([r, g, b], -1)


def chroma_smear(img, shift=2.5, width=11, rng=None, noise=0.012):
    """VHS chroma: low horizontal bandwidth, delayed to the right, noisy."""
    y, cb, cr = ycc(img)
    k = np.ones((1, width), np.float32) / width
    cb = cv2.filter2D(cb, -1, k)
    cr = cv2.filter2D(cr, -1, k)
    M = np.float32([[1, 0, shift], [0, 1, 0]])
    cb = cv2.warpAffine(cb, M, (cb.shape[1], cb.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    cr = cv2.warpAffine(cr, M, (cr.shape[1], cr.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    if rng is not None:
        h, w = cb.shape
        cn = rng.normal(0, noise, (h, w // 8, 2)).astype(np.float32)
        cn = cv2.resize(cn, (w, h), interpolation=cv2.INTER_LINEAR)
        cb += cn[..., 0]
        cr += cn[..., 1]
    return rgb(y, cb, cr)


def sensor_noise(img, rng, base=0.018, shadow=0.045):
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    sig = base + shadow * np.clip(1 - luma * 1.6, 0, 1)
    n = rng.normal(0, 1, luma.shape).astype(np.float32) * sig
    n = cv2.GaussianBlur(n, (0, 0), 0.6)
    return img + n[..., None]


def line_jitter(img, rng, amp=0.6, smooth=7, extra=None):
    """Per-scanline horizontal displacement (VHS time-base error)."""
    h, w = img.shape[:2]
    off = rng.normal(0, 1, h + 40).astype(np.float32)
    off = np.convolve(off, np.ones(smooth) / smooth, "same")[20:20 + h] * amp
    if extra is not None:
        off = off + extra
    mx = (np.arange(w, dtype=np.float32)[None, :] - off[:, None]).astype(np.float32)
    my = np.repeat(np.arange(h, dtype=np.float32)[:, None], w, 1)
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def head_switch(img, rng, rows=16):
    h, w = img.shape[:2]
    band = img[h - rows:].copy()
    for i in range(rows):
        s = int(rng.normal(18, 6)) + i
        band[i] = np.roll(band[i], s, axis=0)
    band = band * 0.8 + rng.normal(0, 0.08, band.shape).astype(np.float32)
    img[h - rows:] = band
    return img


def dropouts(img, rng, rate=0.6):
    h, w = img.shape[:2]
    for _ in range(rng.poisson(rate)):
        y = rng.integers(0, h)
        x = rng.integers(0, w)
        ln = rng.integers(20, 220)
        img[y:y + 2, x:x + ln] = np.clip(img[y:y + 2, x:x + ln] + rng.uniform(0.4, 0.9), 0, 1.2)
    return img


def tracking_band(img, rng, center, height=60, strength=1.0):
    h, w = img.shape[:2]
    y0, y1 = int(max(0, center - height / 2)), int(min(h, center + height / 2))
    if y1 <= y0:
        return img
    seg = img[y0:y1]
    off = rng.normal(0, 25 * strength, y1 - y0).astype(np.float32)
    for i in range(y1 - y0):
        seg[i] = np.roll(seg[i], int(off[i]), axis=0)
    snow = rng.random((y1 - y0, w)).astype(np.float32)
    mask = (snow > 1 - 0.25 * strength)[..., None]
    seg = np.where(mask, 0.85, seg * (1 - 0.3 * strength))
    img[y0:y1] = seg
    return img


def snow(h, w, rng, level=1.0):
    s = rng.random((h // 2, w // 2)).astype(np.float32)
    s = cv2.resize(s, (w, h), interpolation=cv2.INTER_NEAREST)
    s = cv2.GaussianBlur(s, (3, 1), 0)
    return np.repeat((s * level)[..., None], 3, -1)


def roll(img, offset):
    return np.roll(img, int(offset), axis=0)


def rgb_split(img, px):
    out = img.copy()
    M = np.float32([[1, 0, px], [0, 1, 0]])
    out[..., 0] = cv2.warpAffine(img[..., 0], M, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    M = np.float32([[1, 0, -px], [0, 1, 0]])
    out[..., 2] = cv2.warpAffine(img[..., 2], M, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    return out


def bulge(img, cx, cy, radius, k):
    """Magnify around (cx, cy): the picture bulges outward, as if pushed from behind the glass."""
    h, w = img.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = x - cx, y - cy
    r = np.sqrt(dx * dx + dy * dy) / radius
    f = 1 - k * np.exp(-r * r)
    return cv2.remap(img, cx + dx * f, cy + dy * f, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def radial_smear(img, cx, cy, amount, steps=10):
    """Zoom blur from (cx, cy) outward: the face being dragged toward the viewer."""
    acc = np.zeros_like(img)
    h, w = img.shape[:2]
    for i in range(steps):
        s = 1 + amount * i / steps
        M = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])
        acc += cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return acc / steps


def block_displace(img, rng, n=12, size=(40, 140), amp=60):
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(n):
        bh, bw = rng.integers(size[0] // 4, size[0]), rng.integers(size[0], size[1] * 3)
        y, x = rng.integers(0, h - bh), rng.integers(0, w - bw)
        dx, dy = rng.integers(-amp, amp), rng.integers(-amp // 4, amp // 4)
        ys, xs = np.clip(y + dy, 0, h - bh), np.clip(x + dx, 0, w - bw)
        out[y:y + bh, x:x + bw] = img[ys:ys + bh, xs:xs + bw]
    return out
