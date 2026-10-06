#!/bin/sh
# Render every Blender shot used by the film (a few hours on 4 CPU cores).
# Long sequences are rendered in chunks of fresh processes: Cycles' persistent
# data can corrupt subsurface materials after a few hundred frames.
set -e
cd "$(dirname "$0")"
chunks() {   # chunks <script> <first> <last> <size> [args...]
    s=$1; a=$2; b=$3; n=$4; shift 4
    while [ "$a" -le "$b" ]; do
        e=$((a + n - 1)); [ "$e" -gt "$b" ] && e=$b
        python3 "$s" --frames "$a" "$e" "$@"
        a=$((e + 1))
    done
}
python3 scene_stills.py forest
python3 scene_stills.py corridor
python3 scene_stills.py corridor_end
python3 scene_stills.py hallway_her
python3 scene_stills.py hallway_it
# SLIDE 04 at 60 fps (frame numbers: film/p04.py)
python3 scene_containment.py --cam z8
python3 scene_containment.py --cam z4
python3 scene_containment.py --cam cam1 --frames 1 1
chunks scene_containment.py 361 1654 120 --cam cam1
# SLIDE 07 at 60 fps: time-lapse frames, then real time
python3 scene_cell.py --frames 1 540 --step 12
chunks scene_cell.py 541 1261 120
python3 scene_cell.py --empty
