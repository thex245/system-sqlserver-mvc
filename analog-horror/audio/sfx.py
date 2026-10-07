"""Procedural sound design helpers (48 kHz mono float32)."""
import math
import numpy as np
from scipy import signal

SR = 48000


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def db(x):
    return 10 ** (x / 20)


def bandpass(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x, f, order=4):
    sos = signal.butter(order, f, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def highpass(x, f, order=4):
    sos = signal.butter(order, f, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def pink(n, rng):
    w = rng.normal(0, 1, n)
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, w)


def room_ir(rt60=0.9, dur=1.6, rng=None, predelay=0.012, bright=6000):
    rng = rng or np.random.default_rng(0)
    n = int(dur * SR)
    t = np.arange(n) / SR
    tail = rng.normal(0, 1, n) * np.exp(-6.91 * t / rt60)
    tail = lowpass(tail, bright)
    ir = np.zeros(n + int(predelay * SR))
    ir[0] = 1.0
    for d, g in ((0.011, 0.5), (0.017, 0.4), (0.023, 0.33), (0.031, 0.25), (0.043, 0.2)):
        ir[int(d * SR)] += g * (1 if rng.random() > 0.5 else -1)
    ir[int(predelay * SR):] += tail * 0.18
    return ir / np.max(np.abs(ir))


def reverb(x, ir, wet=0.3):
    y = signal.fftconvolve(x, ir)[:len(x)]
    y = y / (np.max(np.abs(y)) + 1e-9) * (np.max(np.abs(x)) + 1e-9)
    return (1 - wet) * x + wet * y


def place(buf, x, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf) or i + len(x) <= 0:
        return
    a, b = max(0, i), min(len(buf), i + len(x))
    buf[a:b] += x[a - i:b - i] * gain


def modal(freqs, decays, amps, dur, rng, jitter=0.02):
    t = t_(dur)
    out = np.zeros_like(t)
    for f, d, a in zip(freqs, decays, amps):
        f = f * (1 + rng.uniform(-jitter, jitter))
        out += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    click = rng.normal(0, 1, len(t)) * np.exp(-t / 0.0015) * 0.3
    return out + highpass(click, 2000)


def clink_cutlery(rng):
    base = rng.uniform(1800, 3200)
    return modal([base, base * 2.31, base * 3.93, base * 5.1], [0.05, 0.03, 0.02, 0.012], [1, 0.6, 0.4, 0.25], 0.25, rng)


def clink_glass(rng):
    base = rng.uniform(1300, 1900)
    return modal([base, base * 2.76, base * 5.4], [0.6, 0.35, 0.2], [1, 0.45, 0.2], 1.2, rng, 0.005)


def plate_scrape(rng, dur=0.5):
    n = pink(int(dur * SR), rng)
    env = np.sin(np.pi * np.linspace(0, 1, len(n))) ** 2
    return bandpass(n, 1500, 6000) * env * 0.4


def thump(freq=80, dur=0.5, rng=None):
    t = t_(dur)
    f = freq * (1 + 0.8 * np.exp(-t / 0.015))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
    n = lowpass((rng or np.random.default_rng()).normal(0, 1, len(t)), 900) * np.exp(-t / 0.03)
    return norm(x + 0.6 * n)


def footstep(rng):
    t = t_(0.18)
    n = rng.normal(0, 1, len(t)) * np.exp(-t / 0.012)
    return norm(bandpass(n, 300, 5000) + 0.4 * np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.03)) * 0.5


def door_swing(rng, dur=3.0):
    t = t_(dur)
    sq = np.sin(2 * np.pi * (700 + 150 * np.sin(2 * np.pi * 1.2 * t)) * t) * np.exp(-t / 0.5) * 0.12
    out = bandpass(sq + rng.normal(0, 0.02, len(t)), 400, 3000)
    for k in range(5):           # flap thuds as it swings back and forth
        place(out, thump(110, 0.3, rng) * 0.5 * 0.55 ** k, 0.55 + k * 0.45)
    return out


def rain(dur, rng):
    n = int(dur * SR)
    bed = bandpass(pink(n, rng), 400, 7000) * 0.25
    drops = np.zeros(n)
    for _ in range(int(dur * 60)):
        place(drops, modal([rng.uniform(2500, 6000)], [0.006], [1], 0.02, rng), rng.uniform(0, dur), rng.uniform(0.02, 0.1))
    return lowpass(bed + drops, 3500)       # heard through the window glass


def car_pass(dur, rng):
    t = t_(dur)
    n = pink(len(t), rng)
    env = np.exp(-((t - dur * 0.45) / (dur * 0.22)) ** 2)
    hiss = bandpass(n, 300, 6000) * env
    rumble = lowpass(rng.normal(0, 1, len(t)), 200) * env
    return norm(hiss * 0.7 + rumble * 0.5) * 0.6


def hum(dur, f0=60.0, rng=None):
    t = t_(dur)
    x = sum(a * np.sin(2 * np.pi * f0 * k * t + k) for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (5, 0.2), (7, 0.1)))
    return x * 0.1


def ring_drop(rng, spin=1.6):
    """Ring lands on the tablecloth, bounces and spins down (Euler's disk rattle)."""
    out = np.zeros(int((spin + 0.6) * SR))
    place(out, modal([3900, 6100, 8800], [0.04, 0.025, 0.015], [1, 0.5, 0.3], 0.2, rng), 0.0, 0.8)
    place(out, modal([3900, 6100], [0.03, 0.02], [1, 0.5], 0.15, rng), 0.09, 0.35)
    t, rate = 0.16, 9.0
    while t < spin:
        amp = 0.25 * (1 - t / spin) ** 0.6
        place(out, modal([rng.uniform(3500, 4300), 6400], [0.012, 0.008], [1, 0.4], 0.04, rng), t, amp)
        rate *= 1.07
        t += 1.0 / rate
    return lowpass(out, 5000)     # damped by the linen


def vhs_audio(x, rng, wow=0.0025, flutter=0.0009):
    """Tape speed variations + bandwidth of linear VHS audio + hiss + soft saturation."""
    n = len(x)
    tt = np.arange(n) / SR
    drift = wow * np.sin(2 * np.pi * 0.45 * tt + 1.0) + flutter * np.sin(2 * np.pi * 6.3 * tt)
    pos = np.arange(n) + np.cumsum(drift)
    y = np.interp(pos, np.arange(n), x)
    y = bandpass(y, 90, 9500, 2)
    y = np.tanh(y * 1.3) / 1.3
    return y + pink(n, rng) * 0.0045


def cctv_mic(x, drive=1.0):
    """Cheap ceiling microphone + DVR audio: narrow band, compressed, a little crunchy."""
    y = bandpass(x, 220, 5200, 3)
    y = np.tanh(y * 2.2 * drive) / (2.2 * drive) ** 0.6
    return y


def pitch_shift(x, semis):
    r = 2 ** (semis / 12)
    idx = np.arange(0, len(x), r)
    return np.interp(idx, np.arange(len(x)), x)


def stutter(x, sr, grain=0.09, repeats=12, decay=0.92):
    g = x[:int(grain * sr)]
    out = np.concatenate([g * decay ** k * np.hanning(len(g)) ** 0.2 for k in range(repeats)])
    return out


def bitcrush(x, bits=6, hold=6):
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    return np.repeat(y[::hold], hold)[:len(x)]
