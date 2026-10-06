"""VHS / composite-video degradation, applied to every frame.

Works in YIQ like the real signal: luma keeps ~250 lines of horizontal detail
with an edge-enhancement halo, chroma is smeared and delayed sideways, each scan
line jitters, the bottom lines carry head-switching noise, and tracking errors,
dropouts and static can be dialled in per frame through `p`.
"""
import functools

import cv2
import numpy as np

from config import H, W

RGB2YIQ = np.array([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]], np.float32)
YIQ2RGB = np.linalg.inv(RGB2YIQ).astype(np.float32)

DEFAULT = dict(
    noise=0.035,       # luma snow
    streak=0.025,      # horizontally stretched noise
    chroma_noise=0.02,
    jitter=0.35,       # per-line horizontal wobble (px)
    chroma_shift=3.0,  # chroma delay (px)
    chroma_blur=4.5,
    luma_blur=0.9,
    sharpen=0.55,      # edge-enhancement halo
    sat=0.85,
    black=0.035,       # lifted black level
    head_switch=1.0,   # bottom-of-frame tear
    tracking=0.0,      # 0..1 tracking error band(s)
    dropout=0.15,      # rate of white dropout streaks
    roll=0.0,          # 0..1 rolling interference bar
    static=0.0,        # 0..1 blend toward pure static
    wobble=0.25,       # whole-frame horizontal sway (px)
    tear=0.0,          # 0..1 big horizontal tearing (glitch)
    rgb_split=0.0,     # px of extra red/blue misregistration (glitch)
    vignette=0.28,
    warm=(1.03, 1.0, 0.95),
)


@functools.lru_cache(1)
def _grid():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return yy, xx


def _streaks(rng, amp):
    """Noise that is long horizontally and thin vertically (tape grain)."""
    n = rng.standard_normal((H, W // 8)).astype(np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)
    return n * amp


def static_frame(rng):
    n = rng.random((H, W // 2), dtype=np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_NEAREST)
    n = 0.7 * n + 0.3 * _streaks(rng, 1.0) * 0.5 + 0.15
    rows = rng.random(H).astype(np.float32)[:, None] * 0.25
    s = np.clip(n + rows - 0.12, 0, 1)
    return np.repeat(s[..., None], 3, axis=2)


def apply(img, t, rng, p=None):
    q = dict(DEFAULT)
    if p:
        q.update(p)
    p = q
    yy, xx = _grid()
    img = np.clip(img, 0, 1).astype(np.float32)

    if p["static"] > 0:
        img = img * (1 - p["static"]) + static_frame(rng) * p["static"]

    yiq = img @ RGB2YIQ.T
    Y, I, Q = yiq[..., 0], yiq[..., 1], yiq[..., 2]

    # --- luma: limited bandwidth + edge enhancement ringing
    Yb = cv2.GaussianBlur(Y, (0, 0), sigmaX=p["luma_blur"], sigmaY=0.3)
    Y = Yb + p["sharpen"] * (Yb - cv2.GaussianBlur(Yb, (0, 0), sigmaX=2.8, sigmaY=0.2))

    # --- chroma: smeared, delayed, noisy
    cb = p["chroma_blur"]
    I = cv2.GaussianBlur(I, (0, 0), sigmaX=cb, sigmaY=1.0)
    Q = cv2.GaussianBlur(Q, (0, 0), sigmaX=cb * 1.2, sigmaY=1.0)
    sh = p["chroma_shift"]
    M = np.float32([[1, 0, sh], [0, 1, 0]])
    I = cv2.warpAffine(I, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    Q = cv2.warpAffine(Q, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    if p["chroma_noise"]:
        cn = rng.standard_normal((H // 4, W // 32)).astype(np.float32)
        cn = cv2.resize(cn, (W, H), interpolation=cv2.INTER_LINEAR) * p["chroma_noise"]
        I = I + cn
        Q = Q - cn * 0.7

    # --- noise
    Y = Y + rng.standard_normal((H, W)).astype(np.float32) * p["noise"] + _streaks(rng, p["streak"])

    # --- rolling interference bar
    if p["roll"] > 0:
        pos = (t * 0.17) % 1.4 - 0.2
        band = np.exp(-((yy / H - pos) ** 2) / 0.006)
        Y = Y + band * 0.12 * p["roll"] - band * rng.random() * 0.02

    # --- per-line horizontal displacement
    off = rng.standard_normal(H).astype(np.float32) * p["jitter"]
    off = cv2.GaussianBlur(off[:, None], (0, 0), sigmaX=0.1, sigmaY=1.2)[:, 0]
    off += np.sin(t * 2.1) * p["wobble"] + np.sin(t * 7.3 + 1.0) * p["wobble"] * 0.4
    if p["tracking"] > 0:
        nb = 1 + int(p["tracking"] * 2.5)
        for _ in range(nb):
            c = rng.random() * H if p["tracking"] > 0.6 else ((t * 140) % (H * 1.6)) - H * 0.3
            hgt = 6 + rng.random() * 30 * p["tracking"]
            m = np.exp(-((yy[:, 0] - c) ** 2) / (2 * hgt ** 2))
            off += m * (rng.standard_normal(H) * 6 + 14) * p["tracking"]
            # noisy, blown-out lines inside the band
            mask = (m > 0.35)[:, None] & (rng.random((H, W)) < 0.18 * p["tracking"])
            Y = np.where(mask, Y + 0.5, Y)
    if p["tear"] > 0:
        for _ in range(int(1 + p["tear"] * 4)):
            r0 = int(rng.random() * H)
            r1 = min(H, r0 + int(4 + rng.random() * 60 * p["tear"]))
            off[r0:r1] += (rng.random() - 0.5) * 120 * p["tear"]
    # head switching: last ~8 lines torn sideways
    if p["head_switch"] > 0:
        hs = 9
        ramp = np.linspace(0, 1, hs, dtype=np.float32) ** 1.5
        off[-hs:] += ramp * (18 + 10 * rng.random()) * p["head_switch"]
        Y[-hs:] += rng.standard_normal((hs, W)).astype(np.float32) * 0.08 * p["head_switch"]

    mapx = xx + off[:, None]
    yiq = np.dstack([Y, I, Q])
    yiq = cv2.remap(yiq, mapx, yy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # --- dropouts: short white streaks
    nd = rng.poisson(p["dropout"])
    for _ in range(nd):
        y = int(rng.random() * (H - 10))
        x = int(rng.random() * W)
        ln = int(10 + rng.random() * 120)
        yiq[y:y + 1, x:x + ln, 0] = 0.95
        yiq[y:y + 1, x:x + ln, 1:] = 0

    rgb = yiq @ YIQ2RGB.T

    if p["rgb_split"]:
        s = p["rgb_split"]
        rgb[..., 0] = cv2.warpAffine(rgb[..., 0], np.float32([[1, 0, s], [0, 1, 0]]), (W, H),
                                     borderMode=cv2.BORDER_REPLICATE)
        rgb[..., 2] = cv2.warpAffine(rgb[..., 2], np.float32([[1, 0, -s], [0, 1, 0]]), (W, H),
                                     borderMode=cv2.BORDER_REPLICATE)

    # --- tone: saturation, warm cast, lifted blacks, vignette
    g = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    rgb = g[..., None] + (rgb - g[..., None]) * p["sat"]
    rgb = rgb * np.array(p["warm"], np.float32)
    rgb = p["black"] + rgb * (1 - p["black"] * 1.4)
    if p["vignette"]:
        v = 1 - p["vignette"] * (((xx / W - 0.5) * 1.6) ** 2 + ((yy / H - 0.5) * 1.6) ** 2)
        rgb = rgb * v[..., None]
    return np.clip(rgb, 0, 1)
