"""Measure median F0 / voiced ratio / noise floor of candidate reference recordings and
transcribe them with word timestamps so clean ~10 s reference segments can be cut."""
import json, os, sys
import torch  # noqa: F401  (ships cuBLAS/cuDNN DLLs that CTranslate2 needs on Windows)
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
os.environ["PATH"] = os.path.join(os.path.dirname(torch.__file__), "lib") + os.pathsep + os.environ["PATH"]
import numpy as np
import librosa
from faster_whisper import WhisperModel

model = WhisperModel("small.en", device="cuda", compute_type="float16")
report = {}
for path in sys.argv[1:]:
    y, sr = librosa.load(path, sr=16000, mono=True, offset=20, duration=100)
    f0, vflag, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr, frame_length=1024)
    rms = librosa.feature.rms(y=y)[0]
    floor = 20 * np.log10(np.percentile(rms, 5) + 1e-9)
    peak = 20 * np.log10(np.percentile(rms, 95) + 1e-9)
    full, _ = librosa.load(path, sr=16000, mono=True, duration=140)
    segs, _ = model.transcribe(full.astype(np.float32), word_timestamps=False, vad_filter=True)
    sents = []
    for s in segs:
        if s.start > 140:
            break
        sents.append((round(s.start, 2), round(s.end, 2), s.text.strip()))
    report[path] = dict(f0_median=float(np.nanmedian(f0)), voiced=float(np.mean(vflag)),
                        noise_floor_db=float(floor), snr_db=float(peak - floor), sentences=sents)
    print(path, json.dumps({k: v for k, v in report[path].items() if k != "sentences"}))
    for s in sents[:30]:
        print("   ", s)
