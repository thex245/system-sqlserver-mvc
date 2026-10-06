"""16:9 poster / thumbnail from the frozen frame of slide 04 -> output/poster.png"""
import numpy as np
from PIL import Image, ImageDraw

import look
import shots
import vhs
from config import H, OUTPUT, RENDERS, W


def main():
    rng = np.random.default_rng(4)
    import p04
    src = shots.footage_frame(RENDERS / "p04" / "z8" / f"{p04.frame(p04.FREEZE):05d}.png")
    img = shots.cctv_grade(shots.barrel(look.View(src, (0.5, 0.5), 1.15).render(), 0.03))
    lines = ((26, 22, "CAM 01", "la"), (W - 26, 22, "09-17-1986", "ra"), (W - 26, 50, "02:41:29", "ra"),
             (W // 2, 22, "FRAME HOLD", "ma"))
    img = shots._osd_cached(lines).over(img)
    img = vhs.apply(img, 3.0, rng, {"noise": 0.06, "tracking": 0.2, "jitter": 0.8})
    frame = Image.fromarray(look.to_u8(img)).resize((960, 720), Image.LANCZOS)
    P = Image.new("RGB", (1280, 720), (4, 4, 6))
    P.paste(frame, (320, 0))
    edge = np.asarray(P, np.float32)    # fade the frame's left edge into black
    ramp = np.clip((np.arange(1280) - 320) / 140, 0, 1)[None, :, None]
    base = np.full_like(edge, 5)
    edge = base * (1 - ramp) + edge * ramp
    P = Image.fromarray(edge.astype(np.uint8))
    d = ImageDraw.Draw(P)
    f1 = look.font("osd", 78)
    f2 = look.font("monob", 26)
    d.text((48, 250), "DO YOU", font=f1, fill=(232, 232, 228))
    d.text((48, 322), "STILL LOVE", font=f1, fill=(232, 232, 228))
    d.text((48, 394), "ME?", font=f1, fill=(225, 60, 50))
    d.text((52, 500), "TAPE B.C.", font=f2, fill=(150, 160, 170))
    out = OUTPUT / "poster.png"
    P.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
