"""Generate N Chatterbox takes per dialogue line and score them.

usage: python tts_generate.py OUT_DIR TAKES man_ref.wav woman_ref.wav [line ids...]
Writes OUT_DIR/<id>_<k>.wav and OUT_DIR/report.json (whisper transcript, timing, loudness, F0).
"""
import json, os, re, sys, difflib
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
os.environ["PATH"] = os.path.join(os.path.dirname(torch.__file__), "lib") + os.pathsep + os.environ["PATH"]
import numpy as np
import soundfile as sf
import librosa
from chatterbox.tts import ChatterboxTTS
from faster_whisper import WhisperModel

sys.path.insert(0, os.path.dirname(__file__))
from lines import LINES

out, takes, man_ref, woman_ref = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
only = set(sys.argv[5:])
os.makedirs(out, exist_ok=True)
refs = {"man": man_ref, "woman": woman_ref}

tts = ChatterboxTTS.from_pretrained(device="cuda")
asr = WhisperModel("small.en", device="cuda", compute_type="float16")
norm = lambda s: re.sub(r"[^a-z' ]", "", s.lower()).split()

rp = os.path.join(out, "report.json")
report = json.load(open(rp)) if os.path.exists(rp) else {}
for lid, spk, text, exg, cfg, temp in LINES:
    if only and lid not in only:
        continue
    for k in range(takes):
        torch.manual_seed(1000 + k * 7919 + sum(map(ord, lid)))
        wav = tts.generate(text, audio_prompt_path=refs[spk], exaggeration=exg,
                           cfg_weight=cfg, temperature=temp)
        y = wav.squeeze(0).cpu().numpy().astype(np.float32)
        path = os.path.join(out, f"{lid}_{k}.wav")
        sf.write(path, y, tts.sr)
        y16 = librosa.resample(y, orig_sr=tts.sr, target_sr=16000)
        segs, _ = asr.transcribe(y16, word_timestamps=True, language="en")
        words = [dict(w=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3), p=round(w.probability, 3))
                 for s in segs for w in s.words]
        hyp = " ".join(w["w"] for w in words)
        sim = difflib.SequenceMatcher(None, norm(text), norm(hyp)).ratio()
        f0, vf, _ = librosa.pyin(y16, fmin=60, fmax=500, sr=16000, frame_length=1024)
        rms = librosa.feature.rms(y=y)[0]
        nz = np.where(np.abs(y) > 0.02)[0]
        report[f"{lid}_{k}"] = dict(
            line=lid, take=k, text=text, hyp=hyp, sim=round(sim, 3), dur=round(len(y) / tts.sr, 3),
            speech_start=round(nz[0] / tts.sr, 3) if len(nz) else 0, speech_end=round(nz[-1] / tts.sr, 3) if len(nz) else 0,
            peak=float(np.abs(y).max()), rms_db=float(20 * np.log10(np.mean(rms) + 1e-9)),
            f0_med=float(np.nanmedian(f0)) if np.any(vf) else 0.0,
            f0_p90=float(np.nanpercentile(f0, 90)) if np.any(vf) else 0.0,
            words=words)
        r = report[f"{lid}_{k}"]
        print(f"{lid}_{k} sim={r['sim']:.2f} dur={r['dur']:.2f} f0={r['f0_med']:.0f}/{r['f0_p90']:.0f} rms={r['rms_db']:.1f} | {hyp}", flush=True)
        json.dump(report, open(rp, "w"), indent=1)
