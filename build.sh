#!/bin/sh
# Rebuild "DO YOU STILL LOVE ME? (TAPE B.C.)" from scratch.
# Needs: python3 (3.13), ffmpeg, ~2 GB of downloads, 4 CPU cores and a few hours
# (almost all of it is the Blender rendering).
set -e
cd "$(dirname "$0")"

pip3 install -q kokoro-onnx pyworld soundfile scipy opencv-python-headless pillow numpy bpy==5.2.2

python3 film/fetch_assets.py        # fonts, TTS model, characters, face detector, archival photos
python3 film/voice.py               # narrator + human voices
python3 film/detect_faces.py        # where the censor bars go
python3 film/paintings.py           # cave walls and the manuscript
film/blender/render_all.sh          # every 3D shot (CCTV footage, photographs)
python3 film/render.py              # picture: the edit through the VHS pass
python3 film/sound.py               # sound design + mix
python3 film/master.py              # mux, upscale, encode -> output/
