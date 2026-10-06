#!/bin/sh
# Render every Blender shot used by the film (a few hours on 4 CPU cores).
set -e
cd "$(dirname "$0")"
python3 scene_stills.py forest
python3 scene_stills.py corridor
python3 scene_stills.py corridor_end
python3 scene_stills.py hallway_her
python3 scene_stills.py hallway_it
python3 scene_containment.py --cam z8      # SLIDE 04, 60 fps: 8x enhance
python3 scene_containment.py --cam z4      #                  4x enhance
python3 scene_containment.py --cam cam1    #                  the CCTV
python3 scene_cell.py
python3 scene_cell.py --empty
