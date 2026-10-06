"""Timing of the P-04 footage (SLIDE 04), shared by the Blender scene and the edit.
All values are seconds of footage time; the scene renders at 60 fps."""

FPS = 60

STATIC_END = 6.0          # the specimen sits motionless; nothing in the room moves
LATCH = 6.0               # the door handle rattles
DOOR_OPEN = (6.5, 8.3)    # the door swings fully open
WALK1 = (8.2, 9.8)        # employee walks from the corridor to just inside the door
PAUSE = (9.8, 10.9)       # stops in the doorway, looks at it
WALK2 = (10.9, 12.6)      # slow approach
KNEEL = (13.2, 14.7)      # kneels down to its eye level
HEAD_UP = (11.4, 14.8)    # the specimen raises its head, in stages
HAND_OUT = (15.4, 18.8)   # it extends its hand, elbow first
REACH = (19.0, 20.1)      # he reaches back...
HOLD = (20.1, 20.7)       # ...stops short...
RETRACT = (20.7, 21.5)    # ...and pulls his hand back
SKIP = 22.2               # cut: the clock jumps three minutes
SKIP_SECONDS = 187        # 3 min 07 s
SMILE = (23.2, 25.3)      # a thin line opens across the blank face
FLICKERS = [(25.35, 25.40), (25.62, 25.70)]
BLACKOUT = (25.92, 26.30) # the light dies; in the dark it turns its head
STARE = 26.30             # light back: it is looking straight into the camera
ZOOM2 = 26.95             # digital enhance x2 (crop of CAM 01)
ZOOM4 = 27.20             # x4
ZOOM8 = 27.45             # x8, held on its face
FREEZE = 28.85            # frame hold
END = 28.85

ZOOM4_LENS_FACTOR = 4.0
ZOOM8_LENS_FACTOR = 8.0


def frame(t):
    """footage seconds -> Blender frame number"""
    return int(round(t * FPS)) + 1
