"""Natural signing with the ER phrase bank: how often does Uni-Sign rank the right phrase first / in the
top 3, for phrases signed by held-out Deaf signers?

Each test phrase is built from one ASL Citizen test signer's isolated clips (same person, same room),
joined in ASL gloss order, either straight through (no rest between signs) or with short pauses.
This is a proxy: joined isolated signs, not native continuous signing.

  python scripts/eval_phrase_bank.py            # 5 signers
"""
import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from remotezip import RemoteZip

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.unisign.preprocess import build_src_input  # noqa: E402
from medbridge.unisign_runner import NaturalSigner  # noqa: E402
from medbridge.vision import hands_active_rtm  # noqa: E402

URL = "https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"
# Bank phrases whose signs all exist in ASL Citizen, in ASL gloss order.
TEST = {
    "My stomach hurts.": ["STOMACH", "HURT"], "My head hurts.": ["HEAD", "HURT"], "I have a headache.": ["HEADACHE"],
    "My heart hurts.": ["HEART", "HURT"], "My back hurts.": ["BACK", "HURT"], "My arm hurts.": ["ARM1", "HURT"],
    "My ear hurts.": ["EAR", "HURT"], "My eyes hurt.": ["EYES", "HURT"],
    "I feel dizzy.": ["ME", "DIZZY"], "I feel sick.": ["ME", "SICK"], "I feel weak.": ["ME", "WEAK"],
    "I am tired.": ["ME", "TIRED"], "I am cold.": ["ME", "COLD"], "I am hot.": ["ME", "HOT"], "I am scared.": ["ME", "SCARED"],
    "I feel better.": ["ME", "FEEL", "BETTER"], "The pain is worse now.": ["NOW", "PAIN", "WORSE"],
    "I can't breathe.": ["ME", "BREATHE", "CANNOT"], "I vomited.": ["ME", "VOMIT"],
    "I vomited yesterday.": ["YESTERDAY", "ME", "VOMIT"], "I vomited this morning.": ["MORNING", "ME", "VOMIT"],
    "I fell down.": ["ME", "FALL1"], "I was in a car accident.": ["CARACCIDENT"], "I cut myself.": ["ME", "CUT"],
    "I burned myself.": ["ME", "BURN"], "I am bleeding.": ["ME", "BLEED"], "I fainted.": ["ME", "FAINT"],
    "I have a cough.": ["ME", "COUGH"], "I am pregnant.": ["ME", "PREGNANT"], "I need medicine.": ["ME", "NEED", "MEDICINE"],
    "I need water.": ["ME", "NEED", "WATER"], "I need the bathroom.": ["ME", "NEED", "BATHROOM"],
    "I want to sleep.": ["ME", "WANT1", "SLEEP"], "I am hungry.": ["ME", "HUNGRY"], "Please help me.": ["PLEASE", "HELP"],
    "Thank you.": ["THANKYOU"], "Yes.": ["YES"], "No.": ["NO"], "I don't know.": ["DONTKNOW"],
    "I don't understand.": ["ME", "UNDERSTAND", "NOT"], "Please write it down.": ["PLEASE", "WRITE"],
    "I am deaf.": ["ME", "DEAF1"], "Please call my wife.": ["PLEASE", "CALL1", "MY", "WIFE"],
    "The pain started yesterday.": ["YESTERDAY", "PAIN", "START"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signers", type=int, default=5)
    args = ap.parse_args()

    bank = json.loads((ROOT / "data/er_phrases.json").read_text())["patient"]
    assert all(p in bank for p in TEST), [p for p in TEST if p not in bank]
    rows = list(csv.reader(open(ROOT / "data/aslc/ASL_Citizen/splits/test.csv")))[1:]
    need = {g for gl in TEST.values() for g in gl}
    have = {}
    for r in rows:
        if r[2].strip() in need:
            have.setdefault(r[0], {}).setdefault(r[2].strip(), r[1])
    signers = sorted(have, key=lambda p: -len(have[p]))[: args.signers]

    todo = [f for p in signers for f in have[p].values() if not (ROOT / "data/eval/aslc" / f).exists()]
    if todo:
        print(f"fetching {len(todo)} clips…")
        with RemoteZip(URL) as z:
            for f in todo:
                (ROOT / "data/eval/aslc" / f).write_bytes(z.read(f"ASL_Citizen/videos/{f}"))

    signer = NaturalSigner(ROOT / "data/models/openasl_pose_only_slt.pth", phrases=bank)
    cache = {}

    def pose(f):
        if f not in cache:
            cap, ks, ss = cv2.VideoCapture(str(ROOT / "data/eval/aslc" / f)), [], []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                k, s = signer.pose(cv2.resize(frame, (1280, 720)))
                ks.append(k); ss.append(s)
            cache[f] = (ks, ss)
        return cache[f]

    def trimmed(ks, ss, pad):
        act = [i for i, (k, s) in enumerate(zip(ks, ss)) if hands_active_rtm(k, s)]
        if not act:
            return ks, ss
        a, b = max(0, act[0] - pad), min(len(ks), act[-1] + 1 + pad)
        return ks[a:b], ss[a:b]

    for pad, name in ((2, "straight through (no rest between signs)"), (12, "short pauses (~0.4 s)")):
        top1 = top3 = n = 0
        right_scores, wrong_scores, lat = [], [], []
        for p in signers:
            for phrase, glosses in TEST.items():
                if not all(g in have[p] for g in glosses):
                    continue
                ks, ss = [], []
                for g in glosses:
                    k, s = trimmed(*pose(have[p][g]), pad)
                    ks += k; ss += s
                t0 = time.perf_counter()
                ranked = signer.model.rank({k: v.to("mps") for k, v in build_src_input(ks, ss).items()}, bank)
                lat.append((time.perf_counter() - t0) * 1000)
                order = [r for r, _ in ranked]
                n += 1; top1 += order[0] == phrase; top3 += phrase in order[:3]
                (right_scores if order[0] == phrase else wrong_scores).append(ranked[0][1])
        print(f"== {name}: n={n} phrases ({len(signers)} signers, bank of {len(bank)})")
        print(f"   right phrase 1st: {100 * top1 / n:.0f}%   in top 3: {100 * top3 / n:.0f}%   (chance 1st: {100 / len(bank):.1f}%)")
        print(f"   top score when right: median {statistics.median(right_scores):.2f} | when wrong: median {statistics.median(wrong_scores):.2f}")
        print(f"   ranking latency (MPS): p50 {statistics.median(lat):.0f} ms")


if __name__ == "__main__":
    main()
