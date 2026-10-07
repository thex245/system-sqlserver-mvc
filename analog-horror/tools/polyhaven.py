"""Poly Haven (CC0) helper: thumbnails and glTF/texture downloads.

usage:
  python polyhaven.py thumbs OUT_DIR id1 id2 ...
  python polyhaven.py model OUT_DIR RES id1 id2 ...      (glTF + textures)
  python polyhaven.py texture OUT_DIR RES id1 id2 ...    (diff/nor_gl/rough/arm jpgs)
"""
import json, os, sys, urllib.request

UA = {"User-Agent": "VAMA-analog-horror-pipeline/1.0"}


def get(url, dest=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    return data


def thumbs(out, ids):
    for i in ids:
        get(f"https://cdn.polyhaven.com/asset_img/thumbs/{i}.png?width=256&height=256", os.path.join(out, f"{i}.png"))


def model(out, res, ids):
    for i in ids:
        files = json.loads(get(f"https://api.polyhaven.com/files/{i}"))
        g = files["gltf"].get(res) or files["gltf"][sorted(files["gltf"])[0]]
        g = g["gltf"]
        d = os.path.join(out, i)
        get(g["url"], os.path.join(d, os.path.basename(g["url"])))
        for rel, inc in g.get("include", {}).items():
            get(inc["url"], os.path.join(d, rel))
        print("model", i)


def texture(out, res, ids):
    for i in ids:
        files = json.loads(get(f"https://api.polyhaven.com/files/{i}"))
        d = os.path.join(out, i)
        for key in ("Diffuse", "nor_gl", "Rough", "arm", "Displacement"):
            if key in files and res in files[key]:
                f = files[key][res].get("jpg") or files[key][res].get("png")
                get(f["url"], os.path.join(d, f"{key}.{f['url'].rsplit('.', 1)[1]}"))
        print("texture", i)


if __name__ == "__main__":
    cmd, out = sys.argv[1], sys.argv[2]
    if cmd == "thumbs":
        thumbs(out, sys.argv[3:])
    elif cmd == "model":
        model(out, sys.argv[3], sys.argv[4:])
    elif cmd == "texture":
        texture(out, sys.argv[3], sys.argv[4:])
