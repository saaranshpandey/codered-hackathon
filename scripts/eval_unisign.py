"""Gate A: run held-out OpenASL test clips through OUR natural-signing pipeline
(rtmlib pose -> medbridge preprocessing -> Uni-Sign) and compare BLEU-4 with the published 22.67.

Usage: python scripts/eval_unisign.py --pose-mode lightweight --device mps
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import sacrebleu
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.unisign_runner import NaturalSigner  # noqa: E402

CLIPS = ROOT / "data/eval/openasl"
CKPT = ROOT / "data/models/openasl_pose_only_slt.pth"


def clip_pose(signer, path, cache):
    if cache.exists():
        z = np.load(cache)
        return list(z["k"]), list(z["s"]), float(z["fps"])
    cap = cv2.VideoCapture(str(path))
    ks, ss, t0 = [], [], time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        k, s = signer.pose(frame)
        ks.append(k); ss.append(s)
    fps = len(ks) / (time.perf_counter() - t0)
    np.savez(cache, k=np.array(ks), s=np.array(ss), fps=fps)
    return ks, ss, fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose-mode", default="lightweight", choices=["lightweight", "balanced", "performance"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--dtype", default="fp32", choices=["fp32", "bf16"])
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float32
    signer = NaturalSigner(CKPT, device=args.device, dtype=dtype, pose_mode=args.pose_mode)
    manifest = json.loads((CLIPS / "manifest.json").read_text())
    cache_dir = ROOT / f"data/eval/poses/{args.pose_mode}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    refs, hyps, top3_hit, lat, fpss, rows = [], [], 0, [], [], []
    for name, item in list(manifest.items())[: args.limit]:
        ks, ss, fps = clip_pose(signer, CLIPS / item["file"], cache_dir / (item["file"] + ".npz"))
        out = signer.translate(ks, ss)
        cands = [c["text"] for c in out["candidates"]]
        refs.append(item["text"]); hyps.append(cands[0])
        lat.append(out["latency_ms"]); fpss.append(fps)
        rows.append({"name": name, "ref": item["text"], "candidates": out["candidates"], "latency_ms": out["latency_ms"]})
        print(f"[{len(refs)}] REF: {item['text']}\n     HYP: {cands[0]}")

    bleu = sacrebleu.corpus_bleu(hyps, [refs], tokenize="13a")
    chrf = sacrebleu.corpus_chrf(hyps, [refs])
    tag = f"{args.pose_mode}_{args.device}_{args.dtype}"
    (ROOT / f"data/eval/unisign_{tag}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    print(f"\n== {tag}: n={len(refs)}  BLEU-4={bleu.score:.2f} (published 22.67)  chrF={chrf.score:.2f}")
    print(f"   BLEU-1..4 precisions={['%.1f' % p for p in bleu.precisions]}")
    print(f"   translate latency ms: p50={statistics.median(lat):.0f} max={max(lat)}  pose fps (offline) median={statistics.median(fpss):.1f}")


if __name__ == "__main__":
    main()
