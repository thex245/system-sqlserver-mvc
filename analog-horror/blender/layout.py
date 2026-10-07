"""Shared set layout (meters). Characters face world -Y at yaw 0; yaw rotates CCW (+pi/2 faces +X).
A seated character's pelvis xy coincides with the dining_chair_02 origin (seat front at local -Y)."""
import math

ROOM = (7.6, 9.6, 3.2)
CAM_POS = (0.32, 0.32, 2.88)

WINDOWS = [(0.9, 3.3), (3.9, 6.9), (7.5, 9.3)]   # y ranges on the x = ROOM[0] wall
WIN_Z = (0.85, 2.6)

BAR_X0, BAR_X1, BAR_Y = 1.3, 3.6, 8.6             # bar counter spans y [BAR_Y-0.55, BAR_Y]
BAR_STOOLS = (1.8, 2.6, 3.3)
KITCHEN_DOOR = (3.9, 4.8)
KITCHEN_PASS = (5.2, 6.1)
CLOCK_POS = (2.45, 9.58, 2.6)
BOOTHS = (4.4, 6.6)
SCONCES = (3.3, 5.5, 7.7)

# Round table by the window. Seats are opposite each other on the axis that leaves the woman's
# face ~50 degrees off CAM 04 (3/4) while she looks at him; he is seen from behind-3/4 when seated.
COUPLE_TABLE = (6.35, 5.8, 0.0)
COUPLE_TABLE_TOP = 0.746
COUPLE_R = 0.398
SEAT_DIST = 0.62
_A = math.radians(-10.5)               # woman's seat angle around the table
W_SEAT_DIST = 0.66                     # 4 cm further out: the cloth hem clears her thighs
WOMAN_SEAT = (6.35 + W_SEAT_DIST * math.cos(_A), 5.8 + W_SEAT_DIST * math.sin(_A))
MAN_SEAT = (6.35 - SEAT_DIST * math.cos(_A), 5.8 - SEAT_DIST * math.sin(_A))


def yaw_towards(src, dst):
    fx, fy = dst[0] - src[0], dst[1] - src[1]
    return math.atan2(fx, -fy)


WOMAN_YAW = yaw_towards(WOMAN_SEAT, COUPLE_TABLE)
MAN_YAW = yaw_towards(MAN_SEAT, COUPLE_TABLE)
# After the first interference he is on his feet on the far (+Y) side of the table, facing her.
MAN_STAND = (6.42, 6.53)                 # ring + scream (close enough to lean on the table)
MAN_STAND_YAW = yaw_towards(MAN_STAND, WOMAN_SEAT)
MAN_STAND3 = (6.44, 6.72)                # "Stop doing that..." -- further back, his gestures clear the table
MAN_STAND3_YAW = yaw_towards(MAN_STAND3, WOMAN_SEAT)
MAN_CHAIR_PUSHED = ((5.36, 6.02, 0.0), MAN_YAW + math.radians(28))
COUPLE_CHAIRS = [((MAN_SEAT[0], MAN_SEAT[1], 0.0), MAN_YAW), ((WOMAN_SEAT[0], WOMAN_SEAT[1], 0.0), WOMAN_YAW)]
# Final shot: her chair has been pulled back 15 cm from the table and turned to face the lens.
WOMAN_FINAL_SEAT = (6.35 + (W_SEAT_DIST + 0.15) * math.cos(_A), 5.8 + (W_SEAT_DIST + 0.15) * math.sin(_A))
WOMAN_FINAL_YAW = math.atan2(-(CAM_POS[0] - WOMAN_FINAL_SEAT[0]), (CAM_POS[1] - WOMAN_FINAL_SEAT[1]))


def _round_diners(cx, cy, r, angles, tags):
    out = []
    for a, tag in zip(angles, tags):
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        fx, fy = -math.cos(a), -math.sin(a)
        yaw = math.atan2(fx, -fy)
        out.append(dict(tag=tag, pelvis=(px, py), yaw=yaw, chair_pos=(px, py, 0.0)))
    return out


def _rect_diners(cx, cy, tags):
    d = 0.353 + 0.24
    return [dict(tag=tags[0], pelvis=(cx, cy - d), yaw=math.pi, chair_pos=(cx, cy - d, 0.0)),
            dict(tag=tags[1], pelvis=(cx, cy + d), yaw=0.0, chair_pos=(cx, cy + d, 0.0))][:len(tags)]


OTHER_TABLES = [
    dict(name="t1", kind="round", center=(2.4, 3.2, 0.0), diners=_round_diners(2.4, 3.2, 0.62, (math.pi, 0.0), ("t1a", "t1b"))),
    dict(name="t2", kind="rect", center=(6.5, 2.6, 0.0), diners=_rect_diners(6.5, 2.6, ("t2a", "t2b"))),
    dict(name="t3", kind="round", center=(3.6, 6.2, 0.0),
         diners=_round_diners(3.6, 6.2, 0.62, (math.pi, math.radians(60), math.radians(-60)), ("t3a", "t3b", "t3c"))),
    dict(name="t4", kind="rect", center=(6.6, 8.3, 0.0), diners=_rect_diners(6.6, 8.3, ("t4a", "t4b"))),
]
BOOTH_DINERS = [dict(tag="b0a", pelvis=(0.5, BOOTHS[0] - 0.64), yaw=math.pi),
                dict(tag="b0b", pelvis=(0.5, BOOTHS[0] + 0.64), yaw=0.0),
                dict(tag="b1a", pelvis=(0.5, BOOTHS[1] - 0.64), yaw=math.pi)]

PENDANTS = [(6.5, 5.9), (6.5, 2.6), (2.4, 3.2), (3.6, 6.2), (6.6, 8.3)]
CAM_TARGET_WIDE = (5.2, 6.3, 0.15)
CHANDELIER = (4.4, 4.3)
