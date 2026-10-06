"""Detect faces in the archival photographs (OpenCV YuNet) -> build/stills/faces.json.
The compositor uses these boxes to place censor bars; photos.py picks which ones."""
import json
import sys

import cv2
import numpy as np

from config import MODELS, PHOTOS, STILLS


def detect(path, det):
    img = cv2.imread(str(path))
    h, w = img.shape[:2]
    s = 1600 / max(h, w)
    img = cv2.resize(img, (int(w * s), int(h * s)))
    # old photos are low contrast: equalize luminance before detecting
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[..., 0])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    det.setInputSize((img.shape[1], img.shape[0]))
    _, faces = det.detect(img)
    out = []
    for f in (faces if faces is not None else []):
        x, y, fw, fh, conf = f[0], f[1], f[2], f[3], f[-1]
        x, y, fw, fh = float(x), float(y), float(fw), float(fh)
        out.append([round(x / img.shape[1], 4), round(y / img.shape[0], 4),
                    round((x + fw) / img.shape[1], 4), round((y + fh) / img.shape[0], 4), round(float(conf), 3)])
    out.sort(key=lambda b: b[0])
    return out


def main():
    det = cv2.FaceDetectorYN.create(str(MODELS / "face_detection_yunet_2023mar.onnx"), "", (320, 320),
                                    score_threshold=0.55, nms_threshold=0.3, top_k=200)
    res = {}
    for p in sorted(PHOTOS.iterdir()):
        if p.suffix.lower() in (".jpg", ".png", ".jpeg"):
            res[p.name] = detect(p, det)
            print(p.name, len(res[p.name]))
    (STILLS / "faces.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
