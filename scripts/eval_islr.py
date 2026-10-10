"""Gate B: run held-out ASL Citizen test videos (unseen signers) through OUR precise-mode pipeline
(MediaPipe Holistic -> medbridge.islr.preprocess -> ST-GCN) and compare with the published
59.52% top-1 / 82.68% top-5. Also reports accuracy restricted to data/medical_vocab.json.

Only the needed test videos are pulled from the 42.8 GB zip with HTTP range reads.
Usage: python scripts/eval_islr.py --n-random 150 --per-gloss 3
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from remotezip import RemoteZip

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.islr import holistic_to_array, load_gloss_list, load_stgcn, preprocess, topk  # noqa: E402

URL = "https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"
SPLITS = ROOT / "data/aslc/ASL_Citizen/splits"
CLIPS = ROOT / "data/eval/aslc"
POSES = ROOT / "data/eval/aslc_poses"


def video_pose(path):
    """Same extraction as ASL Citizen pose.py: fresh Holistic per video, x/y of 543 points."""
    frames = []
    with mp.solutions.holistic.Holistic(static_image_mode=False, min_detection_confidence=0.5) as holistic:
        cap = cv2.VideoCapture(str(path))
        while True:
            ok, image = cap.read()
            if not ok:
                break
            frames.append(holistic_to_array(holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))))
    return np.array(frames)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-random", type=int, default=150)
    ap.add_argument("--per-gloss", type=int, default=3)
    args = ap.parse_args()

    glosses = load_gloss_list(SPLITS / "train.csv")
    vocab = json.loads((ROOT / "data/medical_vocab.json").read_text())
    model = load_stgcn(ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt", len(glosses))
    test = [r for r in list(csv.reader(open(SPLITS / "test.csv")))[1:]]

    random.seed(0)
    rand = random.sample(test, args.n_random)
    med = []
    for g in vocab:
        med += [r for r in test if r[2].strip() == g][: args.per_gloss]

    CLIPS.mkdir(parents=True, exist_ok=True); POSES.mkdir(parents=True, exist_ok=True)
    need = [r for r in rand + med if not (CLIPS / r[1]).exists()]
    if need:
        with RemoteZip(URL) as z:
            for r in need:
                (CLIPS / r[1]).write_bytes(z.read(f"ASL_Citizen/videos/{r[1]}"))

    def predict(r):
        cache = POSES / (r[1] + ".npy")
        if not cache.exists():
            np.save(cache, video_pose(CLIPS / r[1]))
        import torch
        with torch.no_grad():
            return model(preprocess(np.load(cache)))[0]

    def score(rows, vocab_):
        top1 = top5 = 0
        for r in rows:
            preds = topk(predict(r), glosses, vocab_, k=5)
            truth = vocab_[r[2].strip()] if vocab_ else r[2].strip()
            labels = [p["label"] for p in preds]
            top1 += labels[0] == truth
            top5 += truth in labels
        return 100 * top1 / len(rows), 100 * top5 / len(rows)

    t1, t5 = score(rand, None)
    print(f"Full vocab (2731), {len(rand)} random test clips: top-1 {t1:.1f}%  top-5 {t5:.1f}%  (published 59.5 / 82.7)")
    t1, t5 = score(med, None)
    print(f"Medical glosses, full-vocab decoding, {len(med)} clips: top-1 {t1:.1f}%  top-5 {t5:.1f}%")
    t1, t5 = score(med, vocab)
    print(f"Medical glosses, medical-vocab decoding ({len(set(vocab.values()))} labels): top-1 {t1:.1f}%  top-5 {t5:.1f}%")


if __name__ == "__main__":
    main()
