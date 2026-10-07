"""Downscale Rocketbox TGA textures of background extras to 1024 px (PNG keeps alpha) and
optionally delete the TGA originals to save disk. Usage: python downscale_textures.py SIZE --delete DIR..."""
import sys
from pathlib import Path
from PIL import Image

size = int(sys.argv[1])
delete = "--delete" in sys.argv
for d in [a for a in sys.argv[2:] if a != "--delete"]:
    for tga in Path(d).glob("*.tga"):
        im = Image.open(tga)
        if max(im.size) > size:
            im = im.resize((size, size), Image.LANCZOS)
        out = tga.with_suffix(".png")
        im.save(out, optimize=False, compress_level=3)
        if delete:
            tga.unlink()
        print(out.name, im.size, im.mode)
