"""Camera thread and the two sign engines.

Frames are processed in memory only: pose is extracted, the JPEG for the preview replaces the
previous one, and nothing is written to disk. The model always sees unmirrored frames."""
import itertools
import queue
import threading
import time

import cv2
import numpy as np
import torch

from medbridge import metrics
from medbridge.islr import holistic_to_array, preprocess, topk
from medbridge.segmenter import SignSegmenter

_seg_ids = itertools.count(1)


def hands_active_holistic(arr):
    return bool(arr[33:75].any())


def hands_active_rtm(kps, scores, rest_line=0.85, thr=0.4):
    """A hand counts when it is confidently detected and its wrist is above the rest line
    (hands resting in the lap near the bottom of the frame do not count)."""
    for a, b in ((91, 112), (112, 133)):
        if scores[0, a:b].mean() > thr and kps[0, a, 1] < rest_line:
            return True
    return False


def _round(points):
    return np.round(np.asarray(points, dtype=float), 3).tolist()


class PreciseEngine:
    name = "precise"

    def __init__(self, hub, model, glosses, vocab):
        self.hub, self.model, self.glosses, self.vocab = hub, model, glosses, vocab
        self.seg = SignSegmenter(start_frames=3, end_frames=10, preroll=8, postroll=8, min_frames=12, max_frames=128)
        self.holistic = None

    def extract(self, frame_bgr):
        if self.holistic is None:
            import mediapipe as mp
            self.holistic = mp.solutions.holistic.Holistic(static_image_mode=False, min_detection_confidence=0.5)
        return holistic_to_array(self.holistic.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)))

    def landmarks(self, arr):
        hands = [_round(arr[a:b]) for a, b in ((33, 54), (54, 75)) if arr[a:b].any()]
        return {"hands": hands, "body": _round(arr[[0, 11, 12, 13, 14, 15, 16]])}

    def on_pose(self, arr):
        for ev in self.seg.push(arr, hands_active_holistic(arr)):
            if ev[0] == "start":
                self.hub.on_sign_status("signing")
            elif ev[0] == "end":
                self._predict(ev[1])
            else:
                self.hub.on_sign_status("idle")
        if self.seg.state == "idle":
            self.hub.on_sign_status("hands" if hands_active_holistic(arr) else "idle")

    def cancel(self):
        self.seg.force_end()

    def force_end(self):
        clip = self.seg.force_end()
        if clip:
            self._predict(clip)

    def _predict(self, clip):
        self.hub.on_sign_status("recognizing")
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(preprocess(np.array(clip)))[0]
        preds = topk(logits, self.glosses, self.vocab, k=5)
        latency = round((time.perf_counter() - t0) * 1000)
        self.hub.on_sign_prediction(next(_seg_ids), preds, latency_ms=latency)
        metrics.log("precise.prediction", latency_ms=latency, frames=len(clip),
                    top=[(p["label"], round(p["p"], 3)) for p in preds[:3]])
        self.hub.on_sign_status("idle")


class NaturalEngine:
    """Natural signing is recorded between an explicit Start and Done (tap or Space). Hand height is
    not used to end a sentence: signs like STOMACH are made low in a webcam frame and looked like rest."""
    name = "natural"
    MIN_FRAMES = 15
    MAX_FRAMES = 900  # 30 s safety cap; Uni-Sign subsamples long clips to 256 frames itself

    def __init__(self, hub, signer, rest_line=0.85, background=True):
        self.hub, self.signer, self.rest_line = hub, signer, rest_line
        self.clip = None  # list of poses while recording
        self.background = background
        self.busy = False  # a sentence is being translated; keep showing "translating"
        if background:
            self.jobs = queue.Queue()
            threading.Thread(target=self._worker, daemon=True, name="translate").start()

    def extract(self, frame_bgr):
        return self.signer.pose(frame_bgr)

    def landmarks(self, pose):
        k, s = pose
        hands = [_round(k[0, a:b]) for a, b in ((91, 112), (112, 133)) if s[0, a:b].mean() > 0.4]
        return {"hands": hands, "body": _round(k[0, [0, 5, 6, 7, 8, 9, 10]])}

    def start(self):
        if self.busy or self.clip is not None:
            return
        self.clip = []
        self.hub.on_sign_status("signing")

    def cancel(self):
        self.clip = None

    def on_pose(self, pose):
        if self.clip is not None:
            self.clip.append(pose)
            if len(self.clip) >= self.MAX_FRAMES:
                self._finish()
        elif not self.busy:
            self.hub.on_sign_status("hands" if hands_active_rtm(*pose, rest_line=self.rest_line) else "idle")

    def force_end(self):
        if self.clip is not None:
            self._finish()

    def _finish(self):
        clip, self.clip = self.clip, None
        if len(clip) < self.MIN_FRAMES:
            self.hub.on_sign_status("idle")
            return
        self.busy = True
        self.hub.on_sign_status("translating")
        if self.background:
            self.jobs.put(clip)
        else:
            self._translate(clip)

    def _worker(self):
        while True:
            self._translate(self.jobs.get())

    def _translate(self, clip):
        out = self.signer.translate([k for k, _ in clip], [s for _, s in clip])
        out["seg_id"] = next(_seg_ids)
        metrics.log("natural.sentence", latency_ms=out["latency_ms"], frames=len(clip),
                    scores=[round(c["score"], 3) for c in out["candidates"]])
        self.hub.on_sentence(out)
        self.busy = False
        self.hub.on_sign_status("idle")


MAX_WIDTH = 1280


def _open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


class Vision:
    """Owns the camera. A capture thread keeps only the newest frame; the processing thread runs
    the active engine on whatever is newest, so slow frames drop old ones instead of queueing."""

    def __init__(self, hub, camera_index, engines, mode="natural", capture=_open_camera):
        self.hub, self.camera_index, self.engines, self.mode = hub, camera_index, engines, mode
        self.capture = capture
        self.jpeg, self.fps = None, 0.0
        self.frame_ready = threading.Condition()
        self._latest, self._seq = None, 0
        self._new_frame = threading.Condition()
        self._force_end = False
        self._start = False

    def start_signing(self):
        self._start = True

    def set_mode(self, mode):
        self.mode = mode

    def force_end(self):
        self._force_end = True

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="vision").start()

    def _capture_loop(self, cap):
        while True:
            ok, frame = cap.read()
            if not ok:
                self.hub.on_sign_status("no_camera")
                time.sleep(0.5)
                continue
            if frame.shape[1] > MAX_WIDTH:  # e.g. the MacBook camera ignores the 720p request
                frame = cv2.resize(frame, (MAX_WIDTH, round(frame.shape[0] * MAX_WIDTH / frame.shape[1])),
                                   interpolation=cv2.INTER_AREA)
            with self._new_frame:
                self._latest, self._seq = frame, self._seq + 1
                self._new_frame.notify()

    def _run(self):
        cap = self.capture(self.camera_index)
        if not cap.isOpened():
            self.hub.on_sign_status("no_camera")
            return
        threading.Thread(target=self._capture_loop, args=(cap,), daemon=True, name="capture").start()
        engine, seen, n, t0 = None, 0, 0, time.perf_counter()
        while True:
            with self._new_frame:
                self._new_frame.wait_for(lambda: self._seq != seen)
                frame, seen = self._latest, self._seq
            if engine is not self.engines[self.mode]:
                engine = self.engines[self.mode]
                engine.cancel()  # drop any half-finished clip from the other mode
                self.hub.on_sign_status("idle")
            if self._start:
                self._start = False
                if hasattr(engine, "start"):
                    engine.start()
            pose = engine.extract(frame)
            engine.on_pose(pose)
            if self._force_end:
                self._force_end = False
                engine.force_end()
            self.hub.stream({"type": "landmarks", "mode": engine.name, **engine.landmarks(pose)})
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            with self.frame_ready:
                self.jpeg = buf.tobytes()
                self.frame_ready.notify_all()
            n += 1
            if n % 30 == 0:
                self.fps = 30 / (time.perf_counter() - t0)
                t0 = time.perf_counter()
                self.hub.stream({"type": "vision.fps", "fps": round(self.fps, 1)})

    def mjpeg(self):
        while True:
            with self.frame_ready:
                self.frame_ready.wait(timeout=1.0)
                jpeg = self.jpeg
            if jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
