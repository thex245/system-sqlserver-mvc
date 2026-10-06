#!/bin/sh
# Render every Blender shot used by the film (≈2-3 h on 4 CPU cores).
set -e
cd "$(dirname "$0")"
python3 scene_stills.py forest
python3 scene_stills.py corridor
python3 scene_stills.py corridor_end
python3 scene_stills.py hallway_her
python3 scene_stills.py hallway_it
python3 scene_containment.py --cam cam2 --frames 541 721
python3 scene_containment.py --cam cam1
python3 scene_cell.py
python3 scene_cell.py --empty
