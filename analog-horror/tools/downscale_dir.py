"""In-place downscale of jpg/png textures larger than SIZE (keeps format/name). usage: SIZE dir..."""
import sys
from pathlib import Path
from PIL import Image

size = int(sys.argv[1])
n = 0
for d in sys.argv[2:]:
    for p in list(Path(d).rglob("*.jpg")) + list(Path(d).rglob("*.png")):
        im = Image.open(p)
        if max(im.size) <= size:
            continue
        s = size / max(im.size)
        im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
        if p.suffix.lower() == ".jpg":
            im.convert("RGB").save(p, quality=92)
        else:
            im.save(p)
        n += 1
print("downscaled", n)
