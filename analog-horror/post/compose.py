"""Compose the final picture: rendered CCTV frames -> CCTV/VHS degradation -> OSD -> glitches -> ffmpeg.

usage: python compose.py RENDER_DIR FREEZE_DIR OUT.mp4 [t0 t1]
RENDER_DIR holds f_00001.png ... (every 2nd film frame); FREEZE_DIR holds z_0000.png ... (15 fps)
and face.json (screen position of her face during the freeze).
"""
import json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import SEG, GLITCHES, FREEZE_AT, FILM_END, FPS, clock_at
import fx
import osd

FFMPEG = os.environ.get("VAMA_FFMPEG", r"D:\SomeoneYouLove_work\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")
W, H = fx.OUT_W, fx.OUT_H
RENDER_DIR = FREEZE_DIR = None
LENS = None
FACE = None


def seg_of(t):
    for name, a, b, _ in [(s[0], s[1], s[2], s[3]) for s in SEG.values()]:
        if a <= t < b:
            return name
    return "end"


def glitch_at(t):
    out = []
    for g0, dur, kind in GLITCHES:
        if g0 <= t < g0 + dur:
            out.append((kind, (t - g0) / dur))
    return out


def load_render(f):
    """Film frame f (1-based) -> its CCTV frame (falls back to the previous one = DVR repeat)."""
    for k in range(0, 6):
        p = os.path.join(RENDER_DIR, f"f_{f - k:05d}.png")
        if os.path.exists(p):
            return fx.to_float(cv2.imread(p))
    return np.zeros((960, 1280, 3), np.float32)


def cctv(img, rng, gain_noise=1.0):
    img = fx.barrel(img, -0.05)
    img = fx.grade_cctv(img)
    img = fx.bloom(img)
    img = fx.vignette(img, 0.32)
    img = cv2.resize(img, (fx.CCTV_W, fx.CCTV_H), interpolation=cv2.INTER_AREA)
    img = fx.unsharp(img, 1.1, 0.75)
    img = fx.sensor_noise(img, rng, 0.016 * gain_noise, 0.04 * gain_noise)
    return img


def vhs(img, rng, jitter=0.7):
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
    img = fx.chroma_smear(img, shift=3.0, width=15, rng=rng)
    img = fx.line_jitter(img, rng, amp=jitter)
    img = fx.head_switch(img, rng, 18)
    img = fx.dropouts(img, rng, 0.35)
    # faint scanline texture + tape hiss in luma
    img = img * (0.97 + 0.03 * (np.arange(H)[:, None, None] % 2))
    img = img + rng.normal(0, 0.012, (H, W, 1)).astype(np.float32)
    return img


def frame(i):
    f = i + 1
    t = i / FPS
    rng = np.random.default_rng(1000 + i)
    seg = seg_of(t)
    gl = glitch_at(t)
    kinds = {k for k, _ in gl}
    if seg == "black":
        if t < 0.7:
            img = fx.snow(H, W, rng, 0.9)
        else:
            img = np.zeros((H, W, 3), np.float32) + 0.02
            img = fx.line_jitter(img + rng.normal(0, 0.01, (H, W, 1)).astype(np.float32), rng)
            if t < 2.9:
                img = osd.composite(img, osd.vcr_items("PLAY \u25b6"), color=(0.85, 0.95, 0.9), blur=0.4)
        return np.clip(img, 0, 1)
    if seg == "end":
        lt = t - SEG["end"][1]
        if lt < 0.4:
            img = fx.snow(H, W, rng, 1.0)
        else:
            img = np.zeros((H, W, 3), np.float32) + 0.015
            img = img + rng.normal(0, 0.01, (H, W, 1)).astype(np.float32)
            if lt < 1.6:
                img = osd.composite(img, osd.vcr_items("STOP \u25a0"), color=(0.85, 0.95, 0.9), blur=0.4)
            if 2.2 < lt < 6.0:
                a = min(1.0, (lt - 2.2) / 0.5) * min(1.0, (6.0 - lt) / 0.6)
                items = [(240, 150, "SEASON 1 - DO YOU STILL LOVE ME?", 24, "mm"),
                         (240, 185, 'TAPE 1: "I DO"', 30, "mm")]
                img = osd.composite(img, items, color=(0.9, 0.9, 0.88), blur=0.6, alpha=a)
                img = fx.line_jitter(img, rng, 0.8)
        return np.clip(img, 0, 1)

    # ---------------------------------------------------------------- picture
    if seg == "freeze":
        k = int((t - FREEZE_AT) * FPS)
        p = os.path.join(FREEZE_DIR, f"z_{k:04d}.png")
        if not os.path.exists(p):
            p = os.path.join(FREEZE_DIR, "z_0000.png")
        img = fx.to_float(cv2.imread(p))
    else:
        img = load_render(f)
    # DVR stutter: every now and then the recorder repeats a frame
    img = cctv(img, rng, 1.25 if seg == "empty" else 1.0)
    zoom = float(LENS[min(i, len(LENS) - 1)]) / 20.0 if LENS is not None else 1.0
    frozen = seg == "freeze"
    clock = clock_at(t) if not frozen else clock_at(FREEZE_AT - 0.01)
    items = osd.cctv_items(t, clock, zoom, rng, frozen=frozen, glitch_digits=frozen or "interference" in kinds)
    img = osd.composite(img, items, blur=0.5)
    jitter = 0.7

    # ---------------------------------------------------------------- freeze: the face pushes through
    if frozen:
        lt = t - FREEZE_AT
        prog = np.clip((lt - 0.35) / 5.2, 0, 1)
        fxp, fyp, fr_ = FACE["x"] * fx.CCTV_W, FACE["y"] * fx.CCTV_H, FACE["r"] * fx.CCTV_W
        if prog > 0:
            img = fx.bulge(img, fxp, fyp, fr_ * (1.6 + 1.2 * prog), 0.55 * prog ** 1.3 * (1 + 0.15 * math.sin(lt * 31)))
            img = img * (1 - 0.6 * prog) + fx.radial_smear(img, fxp, fyp, 0.35 * prog ** 1.5, 8) * (0.6 * prog)
            img = fx.rgb_split(img, 1 + 9 * prog * (0.6 + 0.4 * rng.random()))
            if rng.random() < 0.25 + 0.6 * prog:
                img = fx.block_displace(img, rng, n=int(4 + 26 * prog), amp=int(15 + 70 * prog))
        if 3.75 < lt < 3.82 or 5.18 < lt < 5.24:
            img = 1.0 - img                                  # one-frame negative flashes
        if lt > 5.55:
            img = img * 0.4 + fx.snow(fx.CCTV_H, fx.CCTV_W, rng, 0.8) * 0.6
        jitter = 0.7 + 6 * prog

    # ---------------------------------------------------------------- VHS
    img = vhs(img, rng, jitter)

    # ---------------------------------------------------------------- glitch events
    for kind, p in gl:
        if kind == "sync":
            img = fx.roll(img, (1 - p) ** 2 * H * 0.6)
            img = img * (0.4 + 0.6 * p) + fx.snow(H, W, rng, 0.6) * (1 - p) * 0.6
        elif kind == "tear":
            y = int(H * (0.2 + 0.6 * rng.random()))
            img = fx.tracking_band(img, rng, y, 90, 1.0)
        elif kind == "tracking":
            img = fx.tracking_band(img, rng, H * (1 - p), 140, 0.9)
        elif kind in ("skip", "return"):
            img = fx.block_displace(img, rng, n=20, size=(60, 200), amp=120)
            img = fx.tracking_band(img, rng, H * rng.random(), 200, 1.0)
            if p < 0.4:
                img = img * 0.3 + fx.snow(H, W, rng, 0.7) * 0.7
        elif kind == "interference":
            s = math.sin(math.pi * p) ** 0.6
            img = fx.roll(img, s * rng.normal(0, 120))
            img = img * (1 - 0.75 * s) + fx.snow(H, W, rng, 0.9) * 0.75 * s
            img = fx.tracking_band(img, rng, H * rng.random(), 300 * s + 40, 1.0)
            img = fx.rgb_split(img, 12 * s)
        elif kind == "tape_end":
            img = img * (1 - p) + fx.snow(H, W, rng, 1.0) * p
    return np.clip(img, 0, 1)


def worker(i):
    return (frame(i) * 255 + 0.5).astype(np.uint8).tobytes()


def init(render_dir, freeze_dir):
    global RENDER_DIR, FREEZE_DIR, LENS, FACE
    RENDER_DIR, FREEZE_DIR = render_dir, freeze_dir
    lp = os.path.join(os.path.dirname(render_dir.rstrip("\\/")), "..", "blend", "cam_lens.npy")
    lp = os.environ.get("VAMA_LENS", r"D:\VAMA_work\blend\cam_lens.npy")
    LENS = np.load(lp) if os.path.exists(lp) else None
    fj = os.path.join(freeze_dir, "face.json")
    FACE = json.load(open(fj)) if os.path.exists(fj) else {"x": 0.6, "y": 0.4, "r": 0.06}


def main():
    render_dir, freeze_dir, out = sys.argv[1:4]
    t0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    t1 = float(sys.argv[5]) if len(sys.argv) > 5 else FILM_END
    init(render_dir, freeze_dir)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    idx = list(range(int(t0 * FPS), int(t1 * FPS)))
    with ProcessPoolExecutor(max_workers=int(os.environ.get("VAMA_WORKERS", "6")),
                             initializer=init, initargs=(render_dir, freeze_dir)) as ex:
        for k, buf in enumerate(ex.map(worker, idx, chunksize=4)):
            p.stdin.write(buf)
            if k % 150 == 0:
                print(f"compose {k}/{len(idx)}", flush=True)
    p.stdin.close()
    p.wait()
    print("WROTE", out)


if __name__ == "__main__":
    main()
