"""Sound design and final mix, driven by the edit's cue sheet.

Everything is synthesized here (no samples): tape hiss, mains hum, a slowly
evolving drone, fluorescent room tone, VCR mechanics, projector clicks,
teletype, glitches. Voice lines get per-cue treatments (tape distortion,
escalating failures in slide 10, the clean human reveal). The whole mix then
passes through a "VHS linear audio track": band-limited, wow & flutter, soft
saturation, limiter.

Output: build/audio/mix.wav (48 kHz stereo)
"""
import json

import numpy as np
import soundfile as sf
from scipy import signal

import edit
from config import AUDIO, SR, VOICE

RNG = np.random.default_rng(1997)


# ------------------------------------------------------------------ helpers
def secs(n):
    return int(round(n * SR))


def bp(x, lo=None, hi=None, order=2):
    if lo and hi:
        sos = signal.butter(order, [lo, hi], "band", fs=SR, output="sos")
    elif lo:
        sos = signal.butter(order, lo, "high", fs=SR, output="sos")
    else:
        sos = signal.butter(order, hi, "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)


def noise(n):
    return RNG.standard_normal(n).astype(np.float32)


def pink(n):
    w = noise(n)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    return (signal.lfilter(b, a, w) * 6).astype(np.float32)


def env_adsr(n, a=0.005, r=0.05):
    e = np.ones(n, np.float32)
    na, nr = min(n, secs(a)), min(n, secs(r))
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def expdecay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR)).astype(np.float32)


def sine(f, n, phase=0.0):
    t = np.arange(n) / SR
    if np.ndim(f):
        return np.sin(2 * np.pi * np.cumsum(f) / SR + phase).astype(np.float32)
    return np.sin(2 * np.pi * f * t + phase).astype(np.float32)


def db(x):
    return 10 ** (x / 20)


def ir(length=2.2, damp=4500, tau=0.55, seed=3):
    r = np.random.default_rng(seed)
    n = secs(length)
    x = r.standard_normal(n).astype(np.float32) * expdecay(n, tau)
    x = bp(x, 120, damp)
    x[:secs(0.012)] = 0
    return x / np.sqrt(np.sum(x ** 2))


ROOM = None


def reverb(x, wet=0.3, length=2.2, tau=0.55, damp=4500):
    global ROOM
    h = ir(length, damp, tau)
    y = signal.fftconvolve(x, h)[:len(x) + len(h)].astype(np.float32)
    out = np.zeros(len(y), np.float32)
    out[:len(x)] += x * (1 - wet * 0.5)
    out += y * wet
    return out


def place(buf, x, t, gain=1.0):
    i = secs(t)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    if i < 0:
        x = x[-i:]
        i = 0
        j = min(len(buf), len(x))
    buf[i:j] += x[:j - i] * gain


# ------------------------------------------------------------------ sfx
def sfx_beep(freq=1000, dur=0.2, level=0.15, **_):
    n = secs(dur)
    x = sine(freq, n) * 0.8 + sine(freq * 2, n) * 0.08
    return x * env_adsr(n, 0.004, 0.03) * level


def sfx_click(level=0.3):
    n = secs(0.03)
    x = bp(noise(n), 1500, 9000) * expdecay(n, 0.004)
    return x * level


def sfx_tick(level=0.25, **_):
    n = secs(0.06)
    x = bp(noise(n), 800, 6000) * expdecay(n, 0.006) + sine(180, n) * expdecay(n, 0.01) * 0.6
    return x * level


def sfx_slide_change(level=1.0, **_):
    """Slide projector: mechanical clack, a short carriage rattle, a burst of tape static."""
    n = secs(0.45)
    x = np.zeros(n, np.float32)
    k = bp(noise(secs(0.05)), 300, 5000) * expdecay(secs(0.05), 0.008)
    x[:len(k)] += k * 0.9
    th = sine(95, secs(0.12)) * expdecay(secs(0.12), 0.03)
    x[:len(th)] += th * 0.7
    k2 = bp(noise(secs(0.04)), 600, 7000) * expdecay(secs(0.04), 0.006)
    x[secs(0.17):secs(0.17) + len(k2)] += k2 * 0.6
    st = bp(noise(secs(0.12)), 400, 8000) * env_adsr(secs(0.12), 0.002, 0.08) * 0.25
    x[:len(st)] += st
    return x * 0.5 * level


def sfx_static(dur=1.0, level=0.5, swell=False, hold=False, **_):
    n = secs(dur)
    x = bp(noise(n), 300, 9000) * 0.7 + bp(noise(n), 2000, 7000) * 0.5
    crackle = (RNG.random(n) < 0.004).astype(np.float32) * noise(n) * 4
    x += bp(crackle, 1000, 9000)
    if swell:
        e = np.linspace(0, 1, n) ** 1.5
        if not hold:
            e = e * env_adsr(n, 0.0, dur * 0.45)
    else:
        e = env_adsr(n, 0.01, min(0.2, dur * 0.3))
    return x * e * level * 0.4


def sfx_vcr_insert(**_):
    n = secs(2.2)
    x = np.zeros(n, np.float32)
    thump = sine(np.linspace(110, 45, secs(0.25)), secs(0.25)) * expdecay(secs(0.25), 0.06)
    x[:len(thump)] += thump * 0.8
    for t0 in (0.0, 0.35, 0.62):
        c = sfx_click(0.6)
        x[secs(t0):secs(t0) + len(c)] += c
    motor = sine(np.linspace(40, 62, secs(1.6)), secs(1.6)) * 0.15 + bp(noise(secs(1.6)), 200, 900) * 0.12
    motor *= env_adsr(secs(1.6), 0.3, 0.6)
    x[secs(0.5):secs(0.5) + len(motor)] += motor
    return x * 0.6


def sfx_vcr_stop(**_):
    n = secs(1.0)
    x = np.zeros(n, np.float32)
    c = sfx_click(0.8)
    x[:len(c)] += c
    th = sine(np.linspace(90, 40, secs(0.3)), secs(0.3)) * expdecay(secs(0.3), 0.07)
    x[secs(0.08):secs(0.08) + len(th)] += th * 0.7
    c2 = sfx_click(0.5)
    x[secs(0.4):secs(0.4) + len(c2)] += c2
    return x * 0.7


def sfx_hit(level=0.5, **_):
    n = secs(3.0)
    x = sine(np.linspace(70, 32, n), n) * expdecay(n, 0.7)
    x += bp(noise(n), 40, 400) * expdecay(n, 0.25) * 0.4
    x = np.tanh(x * 1.6)
    return reverb(x, 0.35, 2.5, 0.8, 2000)[:secs(4.5)] * level


def sfx_sub_pulse(level=0.4, **_):
    n = secs(1.2)
    return sine(np.linspace(55, 38, n), n) * expdecay(n, 0.25) * env_adsr(n, 0.02, 0.2) * level


def sfx_flash_hit(level=0.5, **_):
    n = secs(0.35)
    x = bp(noise(n), 500, 8000) * expdecay(n, 0.05) * 0.8
    x += sine(np.linspace(140, 45, n), n) * expdecay(n, 0.12)
    return np.tanh(x * 1.5) * level


def sfx_riser(dur=4.0, level=0.5, **_):
    n = secs(dur)
    tt = np.linspace(0, 1, n, dtype=np.float32)
    f = 120 * (2 ** (tt * 3.0))
    x = sine(f, n) * 0.25 + sine(f * 1.5 + 3, n) * 0.12
    nz = noise(n)
    sos_lo, out = None, np.zeros(n, np.float32)
    # sweeping band of noise, block-wise
    blk = secs(0.05)
    for i in range(0, n, blk):
        c = 300 * (2 ** (tt[i] * 4.5))
        out[i:i + blk] = bp(nz[max(0, i - blk):i + blk], c * 0.7, min(c * 1.4, 20000))[-len(nz[i:i + blk]):]
    x += out * 0.5
    return x * (tt ** 2) * level * 0.5


def sfx_distort_swell(dur=1.2, level=0.45, **_):
    n = secs(dur)
    tt = np.linspace(0, 1, n, dtype=np.float32)
    x = bp(noise(n), 100, 3000) * tt ** 1.5
    x = np.tanh(x * 3 + sine(50, n) * tt * 2) * 0.5
    return x * level


def sfx_stop_noise(**_):
    n = secs(0.25)
    x = bp(noise(n), 200, 9000) * np.linspace(0.2, 1, n) ** 2
    return x * 0.35


def sfx_flicker(dur=0.5, **_):
    """Fluorescent tube stutter: buzz gated on and off."""
    n = secs(dur)
    buzz = np.tanh(sine(120, n) * 3) * 0.3 + bp(noise(n), 2000, 6000) * 0.15
    gate = np.repeat((RNG.random(int(dur * 40) + 1) > 0.45).astype(np.float32), secs(1 / 40))[:n]
    gate = np.pad(gate, (0, n - len(gate)))
    clicks = np.zeros(n, np.float32)
    d = np.flatnonzero(np.diff(gate) != 0)
    for i in d:
        c = sfx_click(0.5)
        clicks[i:i + len(c)] += c[:n - i]
    return (buzz * gate + clicks) * 0.5


def sfx_door(**_):
    n = secs(2.4)
    x = np.zeros(n, np.float32)
    latch = bp(noise(secs(0.08)), 800, 6000) * expdecay(secs(0.08), 0.01)
    x[:len(latch)] += latch * 0.8
    clunk = sine(70, secs(0.3)) * expdecay(secs(0.3), 0.06)
    x[secs(0.05):secs(0.05) + len(clunk)] += clunk * 0.6
    # hinge creak: rough resonant noise with a wandering pitch
    m = secs(1.6)
    f0 = 380 + 140 * np.sin(np.linspace(0, 3, m)) + 60 * RNG.standard_normal(m).cumsum() / np.sqrt(m) * 4
    creak = sine(f0, m) * (0.5 + 0.5 * np.sign(sine(f0 / 9, m))) * 0.25
    creak = bp(creak, 200, 3000) * env_adsr(m, 0.2, 0.5)
    x[secs(0.5):secs(0.5) + m] += creak
    return reverb(x, 0.4, 1.4, 0.35, 3500)[:n] * 0.35


def sfx_steps(end, interval=0.52, t=None, **_):
    count = int((end - t) / interval)
    n = secs(count * interval + 0.4)
    x = np.zeros(n, np.float32)
    for k in range(count):
        m = secs(0.12)
        s = bp(noise(m), 90, 1200) * expdecay(m, 0.02) + sine(85, m) * expdecay(m, 0.03) * 0.5
        s *= 0.8 + 0.4 * RNG.random()
        i = secs(k * interval + RNG.normal(0, 0.015))
        x[max(0, i):max(0, i) + m] += s
    return reverb(x, 0.45, 1.2, 0.3, 2500)[:n] * 0.18


def sfx_enhance(**_):
    n = secs(0.8)
    x = np.zeros(n, np.float32)
    for k in range(4):
        b = sfx_beep(1200 + 300 * k, 0.05, 0.12)
        x[secs(0.15 * k):secs(0.15 * k) + len(b)] += b
    return x


def sfx_freeze(**_):
    n = secs(4.5)
    c = np.zeros(n, np.float32)
    k = sfx_click(0.7)
    c[:len(k)] += k
    hum = np.tanh(sine(59.94, n) * 2) * 0.05 + bp(noise(n), 1500, 4000) * 0.03
    return c + hum * env_adsr(n, 0.05, 1.0)


def sfx_glitch(dur=0.5, level=0.6, **_):
    """Tape/digital glitch: chopped noise, a buzzy squeal, stutter."""
    n = secs(dur)
    x = np.zeros(n, np.float32)
    i = 0
    while i < n:
        seg = secs(RNG.uniform(0.015, 0.07))
        kind = RNG.integers(0, 3)
        if kind == 0:
            s = bp(noise(seg), 500, 9000)
        elif kind == 1:
            s = np.sign(sine(RNG.uniform(200, 1800), seg)) * 0.4
        else:
            s = np.zeros(seg, np.float32)
        x[i:i + seg] = s[:len(x[i:i + seg])]
        i += seg
    return x * level * 0.5


def sfx_type_burst(n=8, interval=0.07, level=0.2, **_):
    """Teletype / terminal key clicks."""
    total = secs(n * interval + 0.2)
    x = np.zeros(total, np.float32)
    for k in range(n):
        m = secs(0.025)
        c = bp(noise(m), 2000, 9000) * expdecay(m, 0.003) + sine(2400, m) * expdecay(m, 0.002) * 0.3
        i = secs(k * interval + RNG.normal(0, interval * 0.08))
        x[max(0, i):max(0, i) + m] += c * (0.7 + 0.5 * RNG.random())
    return x * level


def sfx_alarm(level=0.2, **_):
    n = secs(1.6)
    x = np.zeros(n, np.float32)
    for k in range(4):
        b = sfx_beep(880 if k % 2 == 0 else 660, 0.18, 1.0)
        x[secs(0.4 * k):secs(0.4 * k) + len(b)] += b
    return x * level


def sfx_ff_whine(dur=4.0, level=0.25, **_):
    n = secs(dur)
    f = 2600 + 400 * np.sin(np.linspace(0, 9, n))
    x = sine(f, n) * 0.25 + bp(noise(n), 3000, 8000) * 0.3
    x += np.tanh(sine(np.linspace(140, 160, n), n) * 3) * 0.15
    return x * env_adsr(n, 0.08, 0.15) * level


def sfx_static_swell(dur=3.0, level=0.5, hold=False, **_):
    return sfx_static(dur, level, swell=True, hold=hold)


def sfx_static_burst(dur=1.0, level=0.5, **_):
    x = sfx_static(dur, level)
    if dur > 0.3:
        g = sfx_glitch(dur * 0.6, level * 0.5)
        x[:len(g)] += g
    return x


SFX = {k[4:]: v for k, v in globals().items() if k.startswith("sfx_")}


# ------------------------------------------------------------------ beds
def bed_hiss(n):
    x = bp(noise(n), 300, 10000) * 0.6 + bp(pink(n), 1000, 7000) * 0.5
    flutter = 1 + 0.08 * np.sin(2 * np.pi * 0.4 * np.arange(n) / SR)
    return x * flutter * db(-41)


def bed_hum(n):
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * 59.94 * k * t) for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (5, 0.12), (7, 0.06)))
    return (x * (1 + 0.15 * np.sin(2 * np.pi * 0.07 * t))).astype(np.float32) * db(-46)


def bed_drone(n):
    """A low, slowly breathing chord with a faint unresolved high partial."""
    t = np.arange(n, dtype=np.float32) / SR
    x = np.zeros(n, np.float32)
    for f, a, rate in ((41.2, 1.0, 0.031), (41.45, 0.8, 0.023), (61.7, 0.45, 0.017), (82.6, 0.3, 0.043),
                       (98.0, 0.18, 0.011), (123.3, 0.12, 0.029)):
        x += a * np.sin(2 * np.pi * f * t + 3 * np.sin(2 * np.pi * rate * t)) * (0.7 + 0.3 * np.sin(2 * np.pi * rate * 1.7 * t))
    x = np.tanh(x * 0.9)
    air = bp(pink(n), 150, 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)) * 0.35
    high = (np.sin(2 * np.pi * 1863.0 * t) * 0.012 + np.sin(2 * np.pi * 2479.0 * t) * 0.008) * \
        (0.5 + 0.5 * np.sin(2 * np.pi * 0.021 * t))
    return (x * 0.5 + air + high) * db(-20)


def bed_roomtone(n):
    t = np.arange(n, dtype=np.float32) / SR
    buzz = np.tanh(np.sin(2 * np.pi * 119.88 * t) * 2.5) * 0.25 + np.sin(2 * np.pi * 239.76 * t) * 0.1
    ac = bp(pink(n), 80, 600) * 0.5
    return (buzz * 0.5 + ac) * db(-30)


BEDS = {"hiss": bed_hiss, "hum": bed_hum, "drone": bed_drone, "roomtone": bed_roomtone}


def automation(n, segments, fade=1.2):
    """Gain curve from (t0, t1, level) segments with smooth fades."""
    g = np.zeros(n, np.float32)
    for (t0, t1, lev) in segments:
        a, b = secs(t0), min(n, secs(t1))
        if b <= a:
            continue
        seg = np.full(b - a, lev, np.float32)
        f = min(secs(fade), (b - a) // 2)
        if f:
            seg[:f] *= np.linspace(0, 1, f)
            seg[-f:] *= np.linspace(1, 0, f)
        g[a:b] = np.maximum(g[a:b], seg)
    return g


# ------------------------------------------------------------------ voice treatments
def load_voice(lid):
    x, sr = sf.read(VOICE / f"{lid}.wav", dtype="float32")
    assert sr == SR
    return x


def tape_color(x, wow=0.0025):
    """Gentle tape coloration for the narrator: band-limit, wow, saturation."""
    n = len(x)
    t = np.arange(n) / SR
    pos = np.arange(n) + (np.sin(2 * np.pi * 0.55 * t) * wow + np.sin(2 * np.pi * 6.1 * t) * wow * 0.2) * SR * 0.05
    x = np.interp(np.clip(pos, 0, n - 1), np.arange(n), x).astype(np.float32)
    x = bp(x, 90, 7500)
    return np.tanh(x * 1.3) / np.tanh(1.3)


def v_distort(x):
    """s02d: the audio distorts slightly — wow deepens, a ring-mod shimmer and crush."""
    n = len(x)
    t = np.arange(n) / SR
    k = np.clip(t / (n / SR), 0, 1)
    pos = np.arange(n) + np.sin(2 * np.pi * 3.0 * t) * 0.006 * SR * k
    y = np.interp(np.clip(pos, 0, n - 1), np.arange(n), x).astype(np.float32)
    ring = np.sin(2 * np.pi * 37 * t).astype(np.float32)
    y = y * (1 - 0.35 * k) + y * ring * 0.35 * k
    crush = np.round(y * 24) / 24
    return (y * 0.6 + crush * 0.4).astype(np.float32)


def stutter(x, rng, count=2, seg=0.09):
    """Repeat a few short fragments (broken playback)."""
    out, i = [], 0
    n = len(x)
    cuts = sorted(rng.uniform(0.15, 0.85, count) * n)
    for c in cuts:
        c = int(c)
        out.append(x[i:c])
        frag = x[c:c + secs(seg)]
        for _ in range(int(rng.integers(2, 4))):
            out.append(frag)
        i = c
    out.append(x[i:])
    return np.concatenate(out)


def dropouts(x, rng, count=2, length=0.05):
    y = x.copy()
    for _ in range(count):
        i = int(rng.uniform(0.1, 0.9) * len(x))
        y[i:i + secs(length)] = 0
    return y


def v_glitch(x, level):
    """Slide 10: the narrator starts failing. The first syllable catches and repeats,
    the pitch wavers, tiny dropouts and a growing digital edge — the words stay clear."""
    rng = np.random.default_rng(len(x) + level)
    n0 = secs(0.07 + 0.008 * level)
    head = x[:n0] * env_adsr(n0, 0.002, 0.01)
    reps = [head] * (1 + level // 2)
    x = np.concatenate(reps + [x])
    x = dropouts(x, rng, count=min(level, 2), length=0.015)
    n = len(x)
    t = np.arange(n) / SR
    pos = np.arange(n) + np.sin(2 * np.pi * (1.1 + 0.6 * level) * t) * 0.0025 * level * SR
    x = np.interp(np.clip(pos, 0, n - 1), np.arange(n), x).astype(np.float32)
    steps = {1: 96, 2: 72, 3: 56}[level]
    crushed = np.round(x * steps) / steps
    x = x * 0.6 + crushed * 0.4
    if level >= 3:
        x = x * (1 + 0.12 * np.sign(np.sin(2 * np.pi * 31 * t)))
    return np.tanh(x * (1 + 0.25 * level)).astype(np.float32)


def v_drag(x):
    """The tape drags: playback slows and sinks in pitch over the end of the line."""
    n = len(x)
    u = np.linspace(0, 1, n)
    rate = 1.0 - 0.32 * np.clip((u - 0.45) / 0.55, 0, 1) ** 1.6
    pos = np.cumsum(rate)
    pos = pos[pos < n - 1]
    y = np.interp(pos, np.arange(n), x).astype(np.float32)
    return v_glitch(y, 1)


def v_tape(x):
    """Interview cassette heard through a failing VHS copy: muffled, noisy, wavering."""
    n = len(x)
    t = np.arange(n) / SR
    pos = np.arange(n) + np.sin(2 * np.pi * 0.9 * t) * 0.01 * SR
    y = np.interp(np.clip(pos, 0, n - 1), np.arange(n), x).astype(np.float32)
    y = bp(y, 300, 2600)
    y = y + bp(noise(n), 1000, 5000) * 0.05
    return reverb(y, 0.25, 0.8, 0.15, 3000)


def v_reveal(x):
    """Close, warm, human. A small room around it and nothing else."""
    return reverb(x, 0.18, 1.0, 0.22, 6000)


def v_whisper(x):
    y = reverb(x, 0.45, 2.6, 0.7, 7000)
    return y


def treat(lid, fx):
    x = load_voice(lid)
    if fx == "robot":
        return tape_color(x)
    if fx == "distort":
        return tape_color(v_distort(x))
    if fx == "tape":
        return v_tape(x)
    if fx == "drag":
        return tape_color(v_drag(x))
    if fx.startswith("glitch"):
        return tape_color(v_glitch(x, int(fx[-1])))
    if fx == "reveal":
        return v_reveal(x)
    if fx == "whisper":
        return v_whisper(x)
    return x


# ------------------------------------------------------------------ mix
def vhs_master(x):
    """Linear-track VHS: ~80 Hz-10 kHz, wow & flutter, soft saturation."""
    n = len(x)
    t = np.arange(n) / SR
    drift = (np.sin(2 * np.pi * 0.31 * t) * 0.0012 + np.sin(2 * np.pi * 4.7 * t) * 0.0003) * SR * 0.06
    pos = np.clip(np.arange(n) + drift, 0, n - 1)
    x = np.interp(pos, np.arange(n), x).astype(np.float32)
    x = bp(x, 45, 11000)
    return np.tanh(x * 1.15) / np.tanh(1.15)


def limiter(x, ceiling=db(-1.0)):
    env = np.abs(x)
    win = secs(0.005)
    env = np.maximum.accumulate(env.reshape(-1, 1), axis=1)[:, 0] if False else env
    peak = signal.lfilter([1], [1, -0.9995], env) * (1 - 0.9995)
    peak = np.maximum(env, peak)
    gain = np.minimum(1.0, ceiling / (peak + 1e-9))
    gain = signal.lfilter([0.002], [1, -0.998], gain).astype(np.float32)
    gain = np.minimum(gain, ceiling / (env + 1e-9))
    return (x * gain).astype(np.float32)


def build_mix(tl=None):
    tl = tl or edit.build()
    n = secs(tl.duration + 1.0)
    bus_bed = np.zeros(n, np.float32)
    bus_fx = np.zeros(n, np.float32)
    bus_v = np.zeros(n, np.float32)

    # beds with automation
    for kind, fn in BEDS.items():
        segs = [(b["t0"], min(b["t1"], tl.duration), b["level"]) for b in tl.beds if b["kind"] == kind]
        if not segs:
            continue
        g = automation(n, segs, fade=0.08 if kind in ("hiss", "hum") else 1.5)
        bus_bed += fn(n) * g
    duck = automation(n, [(b["t0"], b["t1"], b["level"]) for b in tl.beds if b["kind"] == "duck"], fade=1.0)
    bus_bed *= 1 - duck * 0.45 / max(1e-6, duck.max() if duck.max() else 1)

    # one-shots
    for c in tl.sfx:
        name, t = c["name"], c["t"]
        kw = {k: v for k, v in c.items() if k not in ("name",)}
        fn = SFX[name]
        x = fn(**kw)
        place(bus_fx, x, t)

    # voices
    for c in tl.voice:
        x = treat(c["id"], c["fx"]) * c["gain"]
        place(bus_v, x, c["t"])
    # gentle room on the narrator (it is a recording played in a room, not a dry file)
    bus_v_room = reverb(bus_v, 0.1, 0.9, 0.18, 5000)[:n]

    # silences: everything but the voice drops out (fast fades)
    gate = np.ones(n, np.float32)
    for (a, b) in tl.silences:
        ia, ib = secs(a), min(n, secs(b))
        f = secs(0.04)
        gate[ia:ib] = 0
        gate[max(0, ia - f):ia] = np.minimum(gate[max(0, ia - f):ia], np.linspace(1, 0, ia - max(0, ia - f)))
        gate[ib:ib + f] = np.minimum(gate[ib:ib + f], np.linspace(0, 1, len(gate[ib:ib + f])))
    # the reveal and the whisper bypass the tape: they should feel too close
    clean = np.zeros(n, np.float32)
    for c in tl.voice:
        if c["fx"] in ("reveal", "whisper", "tape"):
            x = treat(c["id"], c["fx"]) * c["gain"]
            place(clean, x, c["t"])
            i = secs(c["t"])
            bus_v_room[i:i + len(x)] *= 0  # remove the taped copy of these lines
    tape = (bus_bed + bus_fx) * gate * db(-1) + bus_v_room * db(-1.5)
    tape = vhs_master(tape)
    mix = tape + clean * db(-2)

    # stereo: mostly mono (linear track), with a little decorrelated width on the hiss
    width = bp(noise(n), 2000, 9000) * db(-52) * gate
    L, R = mix + width, mix - width
    st = np.stack([L, R], 1)
    # loudness: normalize RMS of the voice-heavy content, then limit
    rms = np.sqrt(np.mean(st ** 2) + 1e-12)
    st = st * (db(-21) / rms)
    st[:, 0] = limiter(st[:, 0])
    st[:, 1] = limiter(st[:, 1])
    out = AUDIO / "mix.wav"
    sf.write(out, st, SR, subtype="PCM_24")
    print("wrote", out, f"{len(st) / SR:.1f}s  peak {20 * np.log10(np.abs(st).max() + 1e-9):.1f} dBFS")
    return out


if __name__ == "__main__":
    tl = edit.build()
    (AUDIO / "cues.json").write_text(json.dumps(tl.cues(), indent=1))
    build_mix(tl)
