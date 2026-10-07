"""Build viseme tracks (Oculus/Rocketbox AA_VI_* blendshapes) for every selected take.

Word timings come from faster-whisper (takes report.json); phonemes from CMUdict, distributed
inside each word with duration weights; co-articulation via overlapping raised-cosine kernels.
A loudness envelope drives extra jaw opening. Output: lipsync.json (30 fps, relative to the
take's speech start).

usage: python lipsync.py TAKES_DIR OUT_JSON
"""
import json, os, re, sys
import numpy as np
import soundfile as sf
import cmudict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from timeline import TAKES

FPS = 30
CMU = cmudict.dict()
V = {  # ARPAbet -> viseme
    "P": "PP", "B": "PP", "M": "PP", "F": "FF", "V": "FF", "TH": "TH", "DH": "TH", "T": "DD", "D": "DD",
    "K": "kk", "G": "kk", "NG": "nn", "CH": "CH", "JH": "CH", "SH": "CH", "ZH": "CH", "S": "SS", "Z": "SS",
    "N": "nn", "L": "nn", "R": "RR", "ER": "RR", "AA": "aa", "AE": "aa", "AH": "aa", "AO": "O", "AW": "aa",
    "AY": "aa", "EH": "E", "EY": "E", "IH": "I", "IY": "I", "Y": "I", "OW": "O", "OY": "O", "UH": "U",
    "UW": "U", "W": "U", "HH": "aa",
}
SECOND = {"AY": "I", "AW": "U", "EY": "I", "OY": "I", "OW": "U"}  # diphthong glides
KEY = {"sil": "AA_VI_00_Sil", "PP": "AA_VI_01_PP", "FF": "AA_VI_02_FF", "TH": "AA_VI_03_TH", "DD": "AA_VI_04_DD",
       "kk": "AA_VI_05_KK", "CH": "AA_VI_06_CH", "SS": "AA_VI_07_SS", "nn": "AA_VI_08_nn", "RR": "AA_VI_09_RR",
       "aa": "AA_VI_10_aa", "E": "AA_VI_11_E", "I": "AA_VI_12_I", "O": "AA_VI_13_O", "U": "AA_VI_14_U"}
VOWELS = {"aa", "E", "I", "O", "U", "RR"}
# per-viseme peak strengths (lips closures must fully close; vowels slightly below 1 to look natural)
PEAK = {"PP": 1.0, "FF": 0.9, "TH": 0.7, "DD": 0.6, "kk": 0.55, "CH": 0.8, "SS": 0.7, "nn": 0.6, "RR": 0.7,
        "aa": 0.85, "E": 0.75, "I": 0.7, "O": 0.85, "U": 0.85}


def phones(word):
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return []
    if w in CMU:
        return [re.sub(r"\d", "", p) for p in CMU[w][0]]
    # crude letter fallback
    out = []
    for ch in w:
        out.append({"a": "AE", "e": "EH", "i": "IH", "o": "AO", "u": "UH", "y": "IY", "b": "B", "c": "K", "d": "D",
                    "f": "F", "g": "G", "h": "HH", "j": "JH", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P",
                    "q": "K", "r": "R", "s": "S", "t": "T", "v": "V", "w": "W", "x": "K", "z": "Z"}.get(ch, "AH"))
    return out


def track(words, n):
    vis = {k: np.zeros(n) for k in KEY}
    t = np.arange(n) / FPS
    for w in words:
        ph = phones(w["w"])
        if not ph:
            continue
        seq = []
        for p in ph:
            seq.append(V.get(p, "aa"))
            if p in SECOND:
                seq.append(SECOND[p])
        wts = np.array([1.7 if s in VOWELS else (0.7 if s in ("PP", "DD", "kk") else 1.0) for s in seq])
        dur = max(w["e"] - w["s"], 0.08)
        edges = w["s"] + np.concatenate([[0], np.cumsum(wts)]) / wts.sum() * dur
        for i, s in enumerate(seq):
            c = (edges[i] + edges[i + 1]) / 2
            half = max((edges[i + 1] - edges[i]) * 0.9, 0.055)
            k = np.clip(1 - np.abs(t - c) / (half * 1.6), 0, 1)
            k = 0.5 - 0.5 * np.cos(np.pi * k)
            vis[s] = np.maximum(vis[s], k * PEAK[s])
    tot = sum(vis[k] for k in KEY if k != "sil")
    vis["sil"] = np.clip(1 - tot, 0, 1) * 0.0  # rest mouth = basis
    scale = np.where(tot > 1.15, 1.15 / np.maximum(tot, 1e-6), 1.0)
    for k in KEY:
        vis[k] = vis[k] * scale
    return vis


def envelope(path, offset, n):
    y, sr = sf.read(path, dtype="float32")
    hop = sr // FPS
    rms = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(len(y) // hop)])
    db = 20 * np.log10(rms + 1e-9)
    e = np.clip((db + 42) / 30, 0, 1)
    start = int(round(offset * FPS))
    e = e[start:start + n]
    return np.pad(e, (0, max(0, n - len(e))))


def main(takes_dir, out_json):
    reps = {}
    for sub in ("", "extra"):
        p = os.path.join(takes_dir, sub, "report.json")
        if os.path.exists(p):
            for k, v in json.load(open(p)).items():
                reps[(sub + "/" + k) if sub else k] = v
    out = {}
    for line, take in TAKES.items():
        r = reps[take]
        start = r["speech_start"]
        words = [dict(w=w["w"], s=w["s"] - start, e=w["e"] - start) for w in r["words"]]
        n = int((r["speech_end"] - start + 0.4) * FPS)
        vis = track(words, n)
        env = envelope(os.path.join(takes_dir, take + ".wav"), start, n)
        out[line] = dict(take=take, speech_start=start, speech_end=r["speech_end"], frames=n,
                         visemes={KEY[k]: [round(float(x), 3) for x in v] for k, v in vis.items() if v.max() > 0},
                         jaw=[round(float(x), 3) for x in env], words=words)
        print(line, take, n, " ".join(w["w"] for w in words))
    json.dump(out, open(out_json, "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
