"""Render the picture: every frame of the edit through the VHS pass.

  python3 render.py                 full render -> build/video/picture.mkv
  python3 render.py --sheet t1 t2…  contact sheet of the given timestamps (QA)
  python3 render.py --range a b     render seconds [a, b) only (for checking a section)

Frames are rendered in parallel chunks, each piped to its own ffmpeg process,
then concatenated losslessly.
"""
import argparse
import multiprocessing as mp
import subprocess
import sys
import time

import numpy as np
from PIL import Image

import look
import vhs
from config import BUILD, FPS, H, W


def render_frame(tl, f):
    t = f / FPS
    shot, lt = tl.at(t)
    rng = np.random.default_rng(f * 7919 + 17)
    img = shot.frame(lt, rng)
    p = shot.fx(lt)
    img = vhs.apply(img, t, rng, p)
    img = shot.post(img, lt, rng)
    return img


def _worker(args):
    a, b, path = args
    import edit
    tl = edit.build()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "8", "-pix_fmt", "yuv444p",
           "-g", "30", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(a, b):
        img = render_frame(tl, f)
        proc.stdin.write(look.to_u8(img).tobytes())
        if (f - a) % 300 == 0:
            el = time.time() - t0
            print(f"[{a}-{b}] frame {f} ({(f - a) / max(el, 1e-6):.1f} fps)", flush=True)
    proc.stdin.close()
    proc.wait()
    return path


def full(workers=4, a=0.0, b=None, out=None):
    import edit
    tl = edit.build()
    n0 = int(a * FPS)
    n1 = int(round((b if b is not None else tl.duration) * FPS))
    vdir = BUILD / "video"
    vdir.mkdir(exist_ok=True)
    chunk = max(1, -(-(n1 - n0) // (workers * 3)))
    jobs = [(s, min(n1, s + chunk), vdir / f"seg_{s:06d}.mkv") for s in range(n0, n1, chunk)]
    with mp.Pool(workers) as pool:
        segs = pool.map(_worker, jobs, chunksize=1)
    lst = vdir / "segments.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
    out = out or vdir / "picture.mkv"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(out)], check=True)
    for p in segs:
        p.unlink()
    print("wrote", out, f"({(n1 - n0) / FPS:.1f}s)")


def sheet(times, path, cols=3, scale=0.5):
    import edit
    tl = edit.build()
    ims = [render_frame(tl, int(round(t * FPS))) for t in times]
    w, h = int(W * scale), int(H * scale)
    rows = -(-len(ims) // cols)
    S = Image.new("RGB", (cols * w, rows * h))
    for i, im in enumerate(ims):
        S.paste(Image.fromarray(look.to_u8(im)).resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
    S.save(path)
    print("wrote", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=float, nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--range", type=float, nargs=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--cols", type=int, default=3)
    a = ap.parse_args()
    if a.sheet:
        sheet(a.sheet, a.out or "/tmp/sheet.jpg", a.cols, a.scale)
    elif a.range:
        full(a.workers, a.range[0], a.range[1], a.out)
    else:
        full(a.workers)
    sys.exit(0)
