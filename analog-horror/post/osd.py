"""DVR / VCR on-screen display layers (drawn at low resolution, upscaled with nearest neighbour)."""
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

FONT = r"D:\VAMA_work\assets\fonts\VT323-Regular.ttf"
OSD_W, OSD_H = 480, 360          # DVR character generator grid
_font_cache = {}


def font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT, size)
    return _font_cache[size]


def _text(d, xy, s, size, anchor="la", fill=255):
    f = font(size)
    x, y = xy
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            if ox or oy:
                d.text((x + ox, y + oy), s, font=f, fill=1, anchor=anchor)   # outline marker
    d.text((x, y), s, font=f, fill=fill, anchor=anchor)


def render_layers(items):
    """items: list of (x, y, text, size, anchor). Returns (fill_mask, outline_mask) at OSD res."""
    im = Image.new("L", (OSD_W, OSD_H), 0)
    d = ImageDraw.Draw(im)
    for x, y, s, size, anchor in items:
        _text(d, (x, y), s, size, anchor)
    a = np.array(im)
    return (a > 128).astype(np.float32), ((a > 0) & (a <= 128)).astype(np.float32)


def composite(img, items, color=(0.95, 0.95, 0.92), blur=0.7, alpha=1.0):
    if not items:
        return img
    fill, outline = render_layers(items)
    h, w = img.shape[:2]
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_NEAREST)
    outline = cv2.resize(outline, (w, h), interpolation=cv2.INTER_NEAREST)
    if blur:
        fill = cv2.GaussianBlur(fill, (0, 0), blur)
        outline = cv2.GaussianBlur(outline, (0, 0), blur)
    img = img * (1 - 0.85 * alpha * outline[..., None])
    img = img * (1 - alpha * fill[..., None]) + alpha * fill[..., None] * np.array(color, np.float32)
    return img


def cctv_items(t, clock, zoom, rng, frozen=False, glitch_digits=False):
    items = [(14, 10, "CAM 04", 26, "la"), (14, 32, "RESTAURANT", 22, "la"),
             (466, 10, "06-14-1997", 26, "ra"), (466, 32, "SAT", 22, "ra")]
    if clock:
        if glitch_digits:
            clock = "".join(c if (not c.isdigit() or rng.random() > 0.55) else str(rng.integers(0, 10)) for c in clock)
        items.append((14, 330, clock, 30, "la"))
    if not frozen and (t * 1.0) % 1.0 < 0.62:
        items.append((466, 330, "REC \u25cf", 26, "ra"))
    elif frozen:
        items.append((466, 330, "REC", 26, "ra"))
    if zoom > 1.12:
        items.append((466, 300, f"ZOOM x{zoom:4.1f}", 22, "ra"))
        items.append((466, 280, "AUTO TRACK", 18, "ra"))
    return items


def vcr_items(label):
    return [(22, 18, label, 34, "la")]
