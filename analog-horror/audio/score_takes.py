"""Add reference-free quality estimates (torchaudio SQUIM: STOI/PESQ/SI-SDR) to a takes report
and print a ranked table per line.

usage: python score_takes.py TAKES_DIR
"""
import json, os, sys, glob
import torch
import torchaudio
import soundfile as sf
import numpy as np

d = sys.argv[1]
rp = os.path.join(d, "report.json")
rep = json.load(open(rp))
model = torchaudio.pipelines.SQUIM_OBJECTIVE.get_model().cuda().eval()
for key, r in rep.items():
    if "pesq" in r:
        continue
    y, sr = sf.read(os.path.join(d, f"{key}.wav"), dtype="float32")
    t = torchaudio.functional.resample(torch.from_numpy(y)[None], sr, 16000).cuda()
    with torch.no_grad():
        stoi, pesq, sisdr = model(t)
    r.update(stoi=float(stoi), pesq=float(pesq), sisdr=float(sisdr))
json.dump(rep, open(rp, "w"), indent=1)

by_line = {}
for key, r in rep.items():
    by_line.setdefault(r["line"], []).append((key, r))
for line in sorted(by_line):
    rows = sorted(by_line[line], key=lambda kr: (-(kr[1]["sim"] >= 0.99), -kr[1]["pesq"]))
    for key, r in rows:
        print(f"{key:7s} sim={r['sim']:.2f} pesq={r['pesq']:.2f} stoi={r['stoi']:.2f} sisdr={r['sisdr']:5.1f} "
              f"dur={r['dur']:.2f} f0={r['f0_med']:.0f}/{r['f0_p90']:.0f} rms={r['rms_db']:.1f} | {r['hyp']}")
