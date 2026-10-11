"""Why was my sign recognized as something else? Records ONE sign the same way precise mode does,
prints the model's top 5, and compares how your hands moved with Deaf signers' reference clips of the
sign you meant and of the sign the model picked.

  python scripts/debug_sign.py --expect HURT              # camera (works while the server runs)
  python scripts/debug_sign.py --expect HURT --video clip.mp4

Saves only landmark coordinates (no video) to data/debug/ so the attempt can be analysed later.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.islr import holistic_to_array, load_gloss_list, load_stgcn, preprocess, topk  # noqa: E402
from medbridge.segmenter import SignSegmenter  # noqa: E402
from medbridge.vision import hands_active_holistic  # noqa: E402

SPLITS = ROOT / "data/aslc/ASL_Citizen/splits"


def frames_from(source):
    cap = cv2.VideoCapture(source) if isinstance(source, str) else cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
    while True:
        ok, f = cap.read()
        if not ok:
            return
        if f.shape[1] > 1280:
            f = cv2.resize(f, (1280, round(f.shape[0] * 1280 / f.shape[1])), interpolation=cv2.INTER_AREA)
        yield f


def record(source, timeout=10):
    """Same segmentation as PreciseEngine. Returns the clip as a (T, 543, 2) array, or None."""
    seg = SignSegmenter(start_frames=3, end_frames=10, preroll=8, postroll=8, min_frames=12, max_frames=128)
    t0 = time.time()
    with mp.solutions.holistic.Holistic(static_image_mode=False, min_detection_confidence=0.5) as holistic:
        for f in frames_from(source):
            arr = holistic_to_array(holistic.process(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
            for ev in seg.push(arr, hands_active_holistic(arr)):
                if ev[0] == "start":
                    print("  ...signing detected")
                elif ev[0] == "end":
                    return np.array(ev[1])
                else:
                    print("  (too short, ignored — sign again)")
            if time.time() - t0 > timeout and seg.state == "idle":
                break
    clip = seg.force_end()
    return np.array(clip) if clip else None


def stats(a):
    """Hand tracking and geometry, in shoulder widths (x right in the image, y down)."""
    r, l = a[:, 33:54].any(axis=(1, 2)), a[:, 54:75].any(axis=(1, 2))
    sw = np.median(np.linalg.norm(a[:, 11] - a[:, 12], axis=1)) or 1.0
    mid = (a[:, 11] + a[:, 12]) / 2
    both = r & l
    out = {"frames": len(a), "right hand %": 100 * r.mean(), "left hand %": 100 * l.mean(), "both hands %": 100 * both.mean()}
    out["hand spacing"] = np.median(np.linalg.norm(a[both, 33] - a[both, 54], axis=1)) / sw if both.any() else float("nan")
    for name, w, present in (("right", 33, r), ("left", 54, l)):
        if present.any():
            out[f"{name} height"] = np.median((a[present, w, 1] - mid[present, 1]) / sw)
            out[f"{name} x-travel"] = np.ptp(a[present, w, 0]) / sw
        else:
            out[f"{name} height"] = out[f"{name} x-travel"] = float("nan")
    return out


def reference(gloss, n=3):
    rows = [r for r in list(csv.reader(open(SPLITS / "test.csv")))[1:] if r[2].strip() == gloss]
    arrs = [np.load(ROOT / "data/eval/aslc_poses" / (r[1] + ".npy")) for r in rows
            if (ROOT / "data/eval/aslc_poses" / (r[1] + ".npy")).exists()][:n]
    if not arrs:
        return None
    s = [stats(a) for a in arrs]
    return {k: float(np.nanmean([x[k] for x in s])) for k in s[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", required=True, help="gloss you are signing, e.g. HURT (see data/medical_vocab.json)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--video", default=None)
    args = ap.parse_args()

    glosses = load_gloss_list(SPLITS / "train.csv")
    vocab = json.loads((ROOT / "data/medical_vocab.json").read_text())
    model = load_stgcn(ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt", len(glosses))
    expect = args.expect.upper()

    if args.video is None:
        print(f"Hands in your lap. Sign {expect} ONCE after the countdown, then put your hands back in your lap.")
        for i in (3, 2, 1):
            print(f"  {i}…"); time.sleep(1)
        print("  GO")
    clip = record(args.video or args.camera)
    if clip is None:
        print("No sign captured: no hands seen, or the movement was too short.")
        return

    with torch.no_grad():
        preds = topk(model(preprocess(clip))[0], glosses, vocab, k=5)
    print("\nModel (ER vocabulary): " + ", ".join(f"{p['label']} {p['p']:.0%}" for p in preds))
    out_dir = ROOT / "data/debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"sign_{expect}_{time.strftime('%H%M%S')}.npy"
    np.save(path, clip)

    top_gloss = preds[0]["glosses"][0]
    cols = [("you", stats(clip)), (f"ref {expect}", reference(expect))]
    if top_gloss != expect:
        cols.append((f"ref {top_gloss}", reference(top_gloss)))
    print(f"\n{'':16s}" + "".join(f"{name:>14s}" for name, _ in cols))
    for key in cols[0][1]:
        print(f"{key:16s}" + "".join(f"{(c[key] if c else float('nan')):14.2f}" for _, c in cols))
    print("\nheight < 0 means above shoulder level; spacing / travel are in shoulder widths.")
    print(f"Saved landmarks (no video): {path}")


if __name__ == "__main__":
    main()
