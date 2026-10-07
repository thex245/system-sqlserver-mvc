"""Download the first 64kbps MP3 of a LibriVox (public domain) archive.org item."""
import json, os, sys, urllib.request

UA = {"User-Agent": "VAMA-analog-horror-pipeline/1.0"}
out_dir = sys.argv[1]
for ident in sys.argv[2:]:
    meta = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://archive.org/metadata/{ident}", headers=UA), timeout=60).read())
    mp3s = sorted(f["name"] for f in meta["files"] if f["name"].endswith("_64kb.mp3"))
    if not mp3s:
        mp3s = sorted(f["name"] for f in meta["files"] if f["name"].endswith(".mp3"))
    name = mp3s[min(1, len(mp3s) - 1)]  # chapter 2 usually skips the LibriVox preamble-heavy opening
    url = f"https://archive.org/download/{ident}/{urllib.request.quote(name)}"
    dest = os.path.join(out_dir, f"{ident}.mp3")
    os.makedirs(out_dir, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(ident, name, os.path.getsize(dest))
