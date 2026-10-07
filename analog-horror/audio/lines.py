"""Dialogue (English localization) + per-line voice direction for Chatterbox.

exaggeration: emotional intensity (0.25 calm .. 2.0 extreme)
cfg: lower = slower/more deliberate pacing and stronger emotion carry-over
"""

LINES = [
    # id,   speaker, text,                                  exaggeration, cfg,  temperature
    ("M01", "man",   "I need to ask you something.",            0.55, 0.40, 0.75),
    ("W01", "woman", "Go ahead.",                               0.40, 0.50, 0.70),
    ("M02", "man",   "Do you know who I am?",                   0.60, 0.40, 0.75),
    ("W02", "woman", "Of course I do.",                         0.35, 0.50, 0.70),
    ("M03", "man",   "Then why do you keep wearing that?",      0.70, 0.40, 0.75),
    ("W03", "woman", "Because... you gave it to me.",           0.45, 0.40, 0.70),
    ("M04", "man",   "I never gave you that ring.",             0.85, 0.35, 0.80),
    ("M05", "man",   "Stop doing that.",                        0.95, 0.35, 0.80),
    ("W04", "woman", "Doing what?",                             0.35, 0.50, 0.70),
    ("M06", "man",   "Pretending.",                             1.00, 0.35, 0.80),
    ("M07", "man",   "I know you're not her.",                  1.00, 0.30, 0.80),
    ("M08", "man",   "I want my wife back.",                    1.20, 0.30, 0.85),
    ("W05", "woman", "I am your wife.",                         0.30, 0.50, 0.65),
    ("M09", "man",   "No.",                                     1.20, 0.30, 0.85),
    ("M10", "man",   "Where is she?! The real one!",            2.00, 0.25, 0.90),
    ("W06", "woman", "Do you still love me?",                   0.30, 0.45, 0.65),
    ("W07", "woman", "I do.",                                   0.30, 0.45, 0.65),
]
