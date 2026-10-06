"""Shared paths and render settings for the TAPE B.C. build pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILM = ROOT / "film"
BUILD = ROOT / "build"
CACHE = BUILD / "cache"          # third-party downloads (fonts, models, photos)
FONTS = CACHE / "fonts"
MODELS = CACHE / "models"
PHOTOS = CACHE / "photos"
MESHES = CACHE / "meshes"
STILLS = BUILD / "stills"        # prepared 2D images (photos, paintings, cards)
RENDERS = BUILD / "renders"      # Blender output (image sequences / stills)
AUDIO = BUILD / "audio"
VOICE = AUDIO / "voice"
OUTPUT = ROOT / "output"

# Internal frame size. VHS carries ~240 lines of real detail, so the picture is
# built at 720x540 (4:3) and upscaled for delivery.
W, H = 720, 540
FPS = 30
SR = 48000                       # audio sample rate of the final mix

for p in (CACHE, FONTS, MODELS, PHOTOS, MESHES, STILLS, RENDERS, AUDIO, VOICE, OUTPUT):
    p.mkdir(parents=True, exist_ok=True)
