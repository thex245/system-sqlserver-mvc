"""Synthesize and process every spoken line.

The narrator is a natural neural TTS voice (Kokoro, af_heart) re-synthesized
through the WORLD vocoder with its pitch pinned to a single note. That keeps
the words clear while removing every trace of human intonation. The "reveal"
line in slide 10 is the same voice with its natural pitch given back.

Output: build/audio/voice/<id>.wav (mono, 48 kHz) + durations.json
"""
import json
import sys

import numpy as np
import pyworld as pw
import soundfile as sf
from scipy import signal

from config import MODELS, SR, VOICE
from lines import LINES

TTS_SR = 24000
PASION = "pɑsjˈoʊn"          # Spanish-ish "pah-SYOHN" instead of espeak's "PASS-ee-ahn"
ROBOT_F0 = 146.0              # the single note the narrator speaks on
VOICES = {                    # kokoro voice, speed
    "narrator": ("af_heart", 0.84),
    "reveal": ("af_heart", 0.78),
    "whisper": ("af_heart", 0.74),
    "employee": ("am_michael", 0.80),
}
SPEED = {"s01c": 0.65, "s05b": 0.75, "s05c": 0.75}   # short lines need slower delivery to stay clear


def phonemize(k, text):
    parts = text.split("Pasión")
    ph = [k.tokenizer.phonemize(p, "en-us") if p.strip() else "" for p in parts]
    return f" {PASION} ".join(ph)


def trim(x, thresh=0.004, pad=0.05, sr=TTS_SR):
    env = np.convolve(np.abs(x), np.ones(240) / 240, mode="same")
    idx = np.where(env > thresh)[0]
    if not len(idx):
        return x
    a = max(0, idx[0] - int(pad * sr))
    b = min(len(x), idx[-1] + int(pad * sr))
    return x[a:b]


def world(x, sr):
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, sr, f0_floor=60, f0_ceil=520, frame_period=5.0)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)
    return f0, sp, ap


def butter(x, sr, lo=None, hi=None, order=4):
    if lo and hi:
        sos = signal.butter(order, [lo, hi], btype="band", fs=sr, output="sos")
    elif lo:
        sos = signal.butter(order, lo, btype="high", fs=sr, output="sos")
    else:
        sos = signal.butter(order, hi, btype="low", fs=sr, output="sos")
    return signal.sosfilt(sos, x)


def to_sr(x, src, dst):
    g = np.gcd(src, dst)
    return signal.resample_poly(x, dst // g, src // g)


def normalize(x, peak=0.89):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def robot(x):
    """Monotone vocoder narrator: flat pitch, buzzy, narrow band, faint metal ring."""
    f0, sp, ap = world(x, TTS_SR)
    voiced = f0 > 0
    f0n = np.where(voiced, ROBOT_F0, 0.0)
    ap = np.where(voiced[:, None], ap * 0.35, ap)         # less breath in voiced frames -> buzzier
    y = pw.synthesize(f0n, sp, ap, TTS_SR, 5.0)
    y = y + 0.28 * np.concatenate([np.zeros(70), y[:-70]])  # ~2.9 ms comb: metallic edge
    y = to_sr(y, TTS_SR, 11025)                              # early-90s sampler bandwidth
    y = np.round(y / np.max(np.abs(y)) * 2047) / 2047        # 12-bit
    y = to_sr(y, 11025, SR)
    y = butter(y, SR, lo=110)
    return normalize(y)


def reveal(x):
    """The same voice, human again: the first syllable still starts on the robot note
    and slides into natural intonation."""
    f0, sp, ap = world(x, TTS_SR)
    voiced = f0 > 0
    n = len(f0)
    ramp = np.clip((np.arange(n) * 5.0 / 1000 - 0.05) / 0.35, 0, 1)  # 50 ms robot, 350 ms morph
    f0n = np.where(voiced, (1 - ramp) * ROBOT_F0 + ramp * f0 * 0.97, 0.0)
    y = pw.synthesize(f0n, sp, ap, TTS_SR, 5.0)
    y = to_sr(y, TTS_SR, SR)
    # close-mic warmth: gentle low shelf + soft saturation
    low = butter(y, SR, hi=300, order=2)
    y = y + 0.5 * low
    y = np.tanh(1.6 * y / np.max(np.abs(y))) / np.tanh(1.6)
    return normalize(butter(y, SR, lo=70), 0.8)


def whisper(x):
    """Unvoiced re-synthesis: all excitation turned to breath."""
    f0, sp, ap = world(x, TTS_SR)
    ap = np.ones_like(ap)
    y = pw.synthesize(np.zeros_like(f0), sp, ap, TTS_SR, 5.0)
    y = to_sr(y, TTS_SR, SR)
    y = butter(y, SR, lo=400, hi=9000)
    return normalize(y, 0.7)


def employee(x):
    """Interview microcassette: band-limited, saturated, slight wow."""
    y = to_sr(x.astype(np.float64), TTS_SR, SR)
    t = np.arange(len(y)) / SR
    wow = 1 + 0.004 * np.sin(2 * np.pi * 0.7 * t) + 0.002 * np.sin(2 * np.pi * 5.3 * t)
    pos = np.cumsum(wow)
    pos = pos[pos < len(y) - 1]
    y = np.interp(pos, np.arange(len(y)), y)
    y = butter(y, SR, lo=280, hi=3200)
    y = np.tanh(3.0 * y / np.max(np.abs(y)))
    return normalize(y, 0.8)


PROCESS = {"narrator": robot, "reveal": reveal, "whisper": whisper, "employee": employee}


def main(only=None):
    from kokoro_onnx import Kokoro
    k = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    raw_dir = VOICE / "raw"
    raw_dir.mkdir(exist_ok=True)
    dur_file = VOICE / "durations.json"
    durs = json.loads(dur_file.read_text()) if dur_file.exists() else {}
    for lid, (speaker, text) in LINES.items():
        if only and lid not in only:
            continue
        voice, speed = VOICES[speaker]
        speed = SPEED.get(lid, speed)
        samples, sr = k.create(phonemize(k, text), voice=voice, speed=speed, is_phonemes=True)
        assert sr == TTS_SR
        x = trim(np.asarray(samples, dtype=np.float64))
        sf.write(raw_dir / f"{lid}.wav", x, TTS_SR)
        y = PROCESS[speaker](x)
        sf.write(VOICE / f"{lid}.wav", y.astype(np.float32), SR)
        durs[lid] = round(len(y) / SR, 3)
        print(f"{lid:6s} {speaker:9s} {durs[lid]:6.2f}s  {text}")
    dur_file.write_text(json.dumps(durs, indent=1))


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
