"""Build a labelled contact sheet from a list of images (used for casting/QA)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

def main(out_path, cols, thumb_w, *paths):
    cols, thumb_w = int(cols), int(thumb_w)
    imgs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        h = int(im.height * thumb_w / im.width)
        imgs.append((Path(p).stem, im.resize((thumb_w, h))))
    th = max(i.height for _, i in imgs) + 18
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * th), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for k, (name, im) in enumerate(imgs):
        x, y = (k % cols) * thumb_w, (k // cols) * th
        sheet.paste(im, (x, y))
        d.text((x + 4, y + im.height + 2), name, fill=(255, 255, 0))
    sheet.save(out_path, quality=90)

if __name__ == "__main__":
    main(*sys.argv[1:])
