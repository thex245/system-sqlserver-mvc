"""Sound design + mix for TAPE 1 — "I DO".  usage: python mix.py OUT.wav

Everything the viewer hears comes "through" the CCTV ceiling microphone and the VHS dub, except
the final "I do." which is unnaturally close and dry.
"""
import json, os, sys
import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "blender"))
from timeline import SEG, LINES, TAKES, GLITCHES, BEATS, FREEZE_AT, FILM_END
import sfx
from sfx import SR, place, norm

AUDIO = r"D:\VAMA_work\audio"
rng = np.random.default_rng(1924)
N = int(FILM_END * SR)
T_EST, T_DIA = SEG["establish"][1], SEG["dialogue"][1]
T_EMPTY, T_END = SEG["empty"][1], SEG["end"][1]
LIVE = (T_EST, FREEZE_AT)          # restaurant alive


def load(path, sr=SR):
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y.astype(np.float64)


def band(a, b):
    return np.arange(int(a * SR), int(b * SR))


bus_room = np.zeros(N)       # everything picked up by the ceiling mic
bus_dry = np.zeros(N)        # bypasses the mic (VCR mechanics, final whisper)
IR = sfx.room_ir(0.85, 1.4, rng)

# ------------------------------------------------------------------------------ dialogue
reports = {}
for sub in ("", "extra"):
    p = os.path.join(AUDIO, "takes", sub, "report.json")
    for k, v in json.load(open(p)).items():
        reports[(sub + "/" + k) if sub else k] = v
dlg = np.zeros(N)
for line, t in LINES.items():
    if line in ("W06", "W07"):
        continue
    take = TAKES[line]
    y = load(os.path.join(AUDIO, "takes", take + ".wav"))
    s0 = reports[take]["speech_start"]
    y = y[int(max(0, s0 - 0.05) * SR):]
    g = sfx.db(-3) if line.startswith("M") else sfx.db(-4.5)
    if line == "M10":
        y = np.tanh(y * 3.0) / 1.2          # the mic overloads on the scream
    place(dlg, y, t - 0.05, g)
dlg = sfx.reverb(dlg, IR, 0.22)
bus_room += dlg

# ------------------------------------------------------------------------------ restaurant murmur (PD LibriVox readers)
srcs = [os.path.join(AUDIO, "refs_raw", f) for f in os.listdir(os.path.join(AUDIO, "refs_raw")) if f.endswith(".mp3")]
mur_len = 24.0
mur = np.zeros(int(mur_len * SR))
for k in range(11):
    y = load(srcs[k % len(srcs)])
    off = rng.uniform(30, max(31, len(y) / SR - mur_len - 5))
    seg = y[int(off * SR):int((off + mur_len) * SR)]
    seg = sfx.pitch_shift(seg, rng.uniform(-2.5, 2.5))[:len(mur)]
    seg = np.pad(seg, (0, len(mur) - len(seg)))
    mur += seg * rng.uniform(0.5, 1.0)
mur = sfx.lowpass(mur, 1400)
mur = sfx.reverb(mur, IR, 0.6)
mur = norm(mur, 0.25)
# a seamless loop (crossfaded) -- it repeats a little too perfectly, which is the point
xf = int(2.0 * SR)
loop = mur[:-xf].copy()
loop[:xf] = loop[:xf] * np.linspace(0, 1, xf) + mur[-xf:] * np.linspace(1, 0, xf)
idx = band(*LIVE)
bed = np.tile(loop, int(np.ceil(len(idx) / len(loop))) + 1)[:len(idx)]
fade = np.minimum(1, np.minimum(np.arange(len(idx)) / (0.4 * SR), (len(idx) - np.arange(len(idx))) / (0.02 * SR)))
bus_room[idx] += bed * fade * sfx.db(-6)

# ------------------------------------------------------------------------------ cutlery, glasses, scrapes
t = LIVE[0]
while t < LIVE[1]:
    t += rng.exponential(0.9)
    r = rng.random()
    x = sfx.clink_cutlery(rng) if r < 0.6 else (sfx.clink_glass(rng) if r < 0.8 else sfx.plate_scrape(rng))
    place(bus_room, sfx.lowpass(x, rng.uniform(3000, 7000)), t, sfx.db(rng.uniform(-30, -20)))

# ------------------------------------------------------------------------------ music from the ceiling speaker
music = load(os.path.join(AUDIO, "music", "sweetheart_1924.mp3"))
music = sfx.bandpass(music, 350, 4200, 3)
music = np.tanh(music * 2.0) / 2.0
music = sfx.reverb(music, IR, 0.5)
mi = band(*LIVE)
mm = np.tile(music, 2)[int(5 * SR):int(5 * SR) + len(mi)]
bus_room[mi] += norm(mm, 1) * sfx.db(-27)
# empty restaurant: the same record, slowed, warbling, stuck on the chorus
emp = band(T_EMPTY + 2.0, BEATS["she_appears"] - 1.6)
chorus = music[int(32 * SR):int(41 * SR)]
slow = sfx.pitch_shift(chorus, -4.0)
tt = np.arange(len(slow)) / SR
slow = np.interp(np.arange(len(slow)) + 900 * np.sin(2 * np.pi * 0.21 * tt), np.arange(len(slow)), slow)
rep = np.tile(slow, 4)[:len(emp)]
env = np.minimum(1, np.arange(len(emp)) / (4 * SR))
bus_room[emp] += norm(rep, 1) * env * sfx.db(-31)

# ------------------------------------------------------------------------------ rain, cars, HVAC
ri = band(*LIVE)
bus_room[ri] += sfx.rain(len(ri) / SR, rng) * sfx.db(-17)          # stops dead when the picture returns empty
for tc in (BEATS["car_pass_1"], BEATS["car_pass_2"]):
    place(bus_room, sfx.car_pass(5.0, rng), tc - 0.3, sfx.db(-14))
bus_room[band(T_EST, T_END)] += sfx.lowpass(sfx.pink(len(band(T_EST, T_END)), rng), 300) * sfx.db(-38)

# ------------------------------------------------------------------------------ waiter: footsteps + swing door
from cast import WAITER, WALK_SPEED   # noqa: E402
for w in WAITER["walks"]:
    k = 0
    tt_ = w["t0"] + 0.2
    while tt_ < w["t1"] - 0.2:
        place(bus_room, sfx.footstep(rng), tt_, sfx.db(-27 - 3 * (k % 2)))
        tt_ += 16.5 / 30
        k += 1
    place(bus_room, sfx.door_swing(rng), w["door_t"] - 0.1, sfx.db(-16))

# ------------------------------------------------------------------------------ ring + slam
T_DROP = BEATS["ring_on_table"] - 0.2
place(bus_room, sfx.ring_drop(rng), T_DROP + 0.21, sfx.db(-6))
slam = sfx.thump(75, 0.7, rng) + sum(sfx.clink_glass(rng)[:int(0.8 * SR)] * 0.25 for _ in range(2))[:int(0.7 * SR)]
place(bus_room, slam, BEATS["slam"], sfx.db(-1))
for k in range(5):
    place(bus_room, sfx.clink_cutlery(rng), BEATS["slam"] + 0.02 + k * 0.03, sfx.db(-14))

# ------------------------------------------------------------------------------ empty restaurant room tone
ei = band(T_EMPTY, T_END)
tone = sfx.hum(len(ei) / SR, 60.0) * 0.5 + sfx.lowpass(sfx.pink(len(ei), rng), 180) * 0.05
bus_room[ei] += tone * sfx.db(-14)
# the stuttering pendant buzzes
buzz = sfx.bandpass(np.sign(np.sin(2 * np.pi * 120 * np.arange(len(ei)) / SR)) * 0.2, 100, 3000)
bus_room[ei] += buzz * sfx.db(-36) * (1 + 0.5 * np.sin(np.arange(len(ei)) / SR * 7))
# drips from the tablecloth edge
t = T_EMPTY + 3.0
while t < BEATS["she_appears"] - 2:
    place(bus_room, sfx.modal([rng.uniform(900, 1300)], [0.05], [1], 0.15, rng), t, sfx.db(-30))
    t += rng.uniform(1.4, 3.2)

# ------------------------------------------------------------------------------ freeze: the scream gets stuck, then her voice
fz = band(FREEZE_AT, T_EMPTY)
m10 = load(os.path.join(AUDIO, "takes", TAKES["M10"] + ".wav"))
s0 = reports[TAKES["M10"]]["speech_start"]
grain_t = FREEZE_AT - LINES["M10"] + s0 - 0.08
grain = m10[int(grain_t * SR):]
st = sfx.stutter(grain, SR, 0.085, 40, 0.97)
st = np.tanh(sfx.bitcrush(st, 5, 4) * 4)
drone = sfx.pitch_shift(np.tile(grain[:int(0.4 * SR)], 30), -14)
frz = np.zeros(len(fz))
frz[:len(st)] += st[:len(frz)] * 0.6
d = drone[:len(frz)]
frz[:len(d)] += d * np.linspace(0, 1, len(d)) * 0.8
frz += sfx.bandpass(rng.normal(0, 1, len(frz)), 200, 8000) * np.linspace(0.05, 0.6, len(frz))
rm = np.sin(2 * np.pi * 37 * np.arange(len(frz)) / SR)
frz = frz * (0.6 + 0.4 * rm)
w06 = load(os.path.join(AUDIO, "takes", TAKES["W06"] + ".wav"))
w06 = w06[int(reports[TAKES["W06"]]["speech_start"] * SR):]
w_low = sfx.pitch_shift(w06, -5)
w_rev = sfx.reverb(w06[::-1], sfx.room_ir(2.5, 3.0, rng), 0.9)[::-1]
voice = np.zeros(len(frz))
place(voice, w_rev * 0.6, LINES["W06"] - FREEZE_AT - 1.2)
place(voice, w06 * 0.9, LINES["W06"] - FREEZE_AT)
place(voice, w_low * 0.7, LINES["W06"] - FREEZE_AT + 0.03)
place(voice, w06 * 0.5, LINES["W06"] - FREEZE_AT + 1.9)            # a second, quieter "do you still love me?"
frz = np.tanh((frz * 0.5 + voice * 1.3) * 1.6)
frz[int(5.55 * SR):] = sfx.bandpass(rng.normal(0, 1, len(frz) - int(5.55 * SR)), 300, 9000) * 0.5
bus_room[fz] = frz * sfx.db(-2)      # nothing else survives the freeze

# ------------------------------------------------------------------------------ glitch sounds
for g0, dur, kind in GLITCHES:
    if kind in ("freeze",):
        continue
    gi = band(g0, g0 + dur)
    x = sfx.bandpass(rng.normal(0, 1, len(gi)), 500, 9000) * 0.5
    if kind in ("interference", "skip", "return", "tape_end"):
        x += np.sign(np.sin(2 * np.pi * rng.uniform(90, 160) * np.arange(len(gi)) / SR)) * 0.25
        bus_room[gi] *= 0.3
    env = np.sin(np.pi * np.linspace(0, 1, len(gi))) ** 0.5
    bus_room[gi] += x * env * sfx.db(-6 if kind != "tear" else -16)

# ------------------------------------------------------------------------------ through the mic, then the tape
mix = sfx.cctv_mic(bus_room, 1.0)
mix[band(0, T_EST)] = 0.0
# "I do." -- close, dry, too intimate for a ceiling microphone
w07 = load(os.path.join(AUDIO, "takes", TAKES["W07"] + ".wav"))
w07 = w07[int(max(0, reports[TAKES["W07"]]["speech_start"] - 0.05) * SR):]
place(bus_dry, sfx.highpass(w07, 120) * sfx.db(-1), LINES["W07"] - 0.05)
# her appearance: the room tone drops out under her
ap = band(BEATS["she_appears"], T_END)
mix[ap] *= 0.35
# VCR mechanics: load + play at the head, stop at the tail
place(bus_dry, sfx.thump(140, 0.25, rng) * 0.4, 0.15)
place(bus_dry, sfx.thump(220, 0.15, rng) * 0.25, 0.5)
place(bus_dry, sfx.thump(160, 0.3, rng) * 0.45, T_END + 0.4)
whirr = sfx.bandpass(rng.normal(0, 1, int(2.0 * SR)), 200, 1200) * 0.03
place(bus_dry, whirr, 0.4)
out = sfx.vhs_audio(mix + bus_dry, rng)
out[band(T_END + 0.6, FILM_END)] *= 0.25
out = out / (np.max(np.abs(out)) + 1e-9) * sfx.db(-1.0)
stereo = np.stack([out, out], 1)
sf.write(sys.argv[1], stereo.astype(np.float32), SR, subtype="PCM_24")
print("WROTE", sys.argv[1], len(out) / SR, "s")
