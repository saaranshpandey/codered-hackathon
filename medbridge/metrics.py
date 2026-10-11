"""Opt-in measurement log (METRICS_LOG=1): timings, scores and sign labels only — never audio,
video, or caption/sentence text. Written to data/metrics.jsonl for the Phase 6 numbers."""
import json
import os
import threading
import time
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data/metrics.jsonl"
_lock = threading.Lock()


def log(event, **fields):
    if os.environ.get("METRICS_LOG") != "1":
        return
    with _lock, open(PATH, "a") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "event": event, **fields}) + "\n")
