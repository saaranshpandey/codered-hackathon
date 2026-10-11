"""Natural-signing mode: rtmlib whole-body pose per frame, Uni-Sign translation per clip."""
import time

import numpy as np
import torch

from medbridge.unisign.model import load_unisign
from medbridge.unisign.preprocess import build_src_input


def select_person(keypoints, scores, thr=0.3):
    """Keep the largest visible person (the signer facing the camera) as person 0,
    in the (1, 133, 2) / (1, 133) layout Uni-Sign reads."""
    best, best_area = None, 0.0
    for i in range(len(keypoints)):
        vis = keypoints[i][scores[i] > thr]
        if len(vis) < 2:
            continue
        area = np.ptp(vis[:, 0]) * np.ptp(vis[:, 1])
        if area > best_area:
            best, best_area = i, area
    if best is None:
        return np.zeros((1, 133, 2)), np.zeros((1, 133))
    return keypoints[best][None], scores[best][None]


def largest_box(bboxes):
    """The patient is the person nearest the camera; posing every detected box (often ~9 on a
    live scene) costs ~3x and the translator only reads one person anyway."""
    bboxes = np.asarray(bboxes)
    if len(bboxes) <= 1:
        return bboxes
    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
    return bboxes[[int(np.argmax(areas))]]


def make_pose(mode="lightweight", pose_device="mps"):
    """rtmlib Wholebody (detector + whole-body pose) with the two models on separate devices:
    the YOLOX detector crashes onnxruntime's CoreML provider, so it stays on CPU, while the RTMW
    pose model runs ~4x faster on CoreML ("mps"). Returns frame -> (keypoints px, scores)."""
    from rtmlib import RTMPose, YOLOX, Wholebody

    m = Wholebody.MODE[mode]
    det = YOLOX(m["det"], model_input_size=m["det_input_size"], backend="onnxruntime", device="cpu")
    pose = RTMPose(m["pose"], model_input_size=m["pose_input_size"], to_openpose=False,
                   backend="onnxruntime", device=pose_device)
    return lambda image: pose(image, bboxes=largest_box(det(image)))


def rel_scores(seq_scores):
    """Softmax over beam scores: the model's relative preference between its candidates."""
    s = np.exp(np.array(seq_scores) - max(seq_scores))
    return (s / s.sum()).tolist()


def top_phrases(ranked, k=3):
    """Best k bank phrases; rel_score is each phrase's share of the softmax over the WHOLE bank."""
    rel = rel_scores([s for _, s in ranked])
    return [{"text": p, "score": s, "rel_score": r} for (p, s), r in list(zip(ranked, rel))[:k]]


class NaturalSigner:
    def __init__(self, ckpt, device="mps", dtype=torch.float32, pose_mode="lightweight", max_length=256, pose_device="mps",
                 phrases=None):
        self.wholebody = make_pose(pose_mode, pose_device)
        self.phrases = list(phrases or [])  # ER phrase bank ranked against each sentence
        self.model, _ = load_unisign(ckpt, lang="English", device=device, dtype=dtype)
        self.device, self.dtype, self.max_length = device, dtype, max_length

    def pose(self, frame_bgr):
        """Returns (keypoints (1,133,2) normalised by W,H; scores (1,133))."""
        kps, scores = self.wholebody(frame_bgr)
        h, w = frame_bgr.shape[:2]
        return select_person(np.asarray(kps) / np.array([w, h])[None, None], np.asarray(scores))

    def translate(self, skeletons, confs):
        t0 = time.perf_counter()
        src = build_src_input(skeletons, confs, self.max_length)
        src = {k: v.to(self.device, self.dtype) if v.is_floating_point() else v.to(self.device)
               for k, v in src.items()}
        out = self.model.translate(src)
        rel = rel_scores([s for _, s in out])
        result = {"candidates": [{"text": t, "score": s, "rel_score": r} for (t, s), r in zip(out, rel)]}
        if self.phrases:
            result["phrases"] = top_phrases(self.model.rank(src, self.phrases))
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000)
        return result
