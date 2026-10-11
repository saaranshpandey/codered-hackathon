"""Fetch held-out OpenASL test clips for offline evaluation of the natural-signing model.

Clips come from YouTube (OpenASL is YouTube-sourced). They are stored only under data/eval/
(gitignored) and used offline to check that our pipeline reproduces the published BLEU.

Usage: python scripts/fetch_eval_clips.py --n 60
"""
import argparse
import collections
import gzip
import json
import pickle
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data/src/Uni-Sign/data/OpenASL/labels.test"
OUT = ROOT / "data/eval/openasl"
NAME_RE = re.compile(r"^(.*)-(\d\d:\d\d:\d\d\.\d+)-(\d\d:\d\d:\d\d\.\d+)\.mp4$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()

    labels = pickle.load(gzip.open(LABELS, "rb"))
    by_video = collections.defaultdict(list)
    for name, item in labels.items():
        yid, start, end = NAME_RE.match(name).groups()
        by_video[yid].append((name, start, end, item["text"]))

    # Prefer videos with many test clips so few downloads cover many clips.
    order = sorted(by_video, key=lambda v: (-len(by_video[v]), v))
    (OUT / "full").mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for yid in order:
        if len(manifest) >= args.n:
            break
        full = OUT / "full" / f"{yid}.mp4"
        if not full.exists():
            r = subprocess.run(
                ["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=720][ext=mp4]/b[height<=720][ext=mp4]",
                 "-o", str(full), "--", yid],
                capture_output=True, text=True)
            if r.returncode != 0 or not full.exists():
                print(f"skip {yid}: unavailable")
                continue
        for name, start, end, text in by_video[yid]:
            if len(manifest) >= args.n:
                break
            clip = OUT / name.replace(":", "_")
            if not clip.exists():
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-ss", start, "-to", end, "-i", str(full),
                     "-an", "-c:v", "libx264", "-crf", "18", str(clip)], check=True)
            manifest[name] = {"file": clip.name, "text": text}
            manifest_path.write_text(json.dumps(manifest, indent=1))
        print(f"{len(manifest)} clips")


if __name__ == "__main__":
    main()
