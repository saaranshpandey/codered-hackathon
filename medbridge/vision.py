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
        if self.seg.state == "idle" and hands_active_holistic(arr):
            self.hub.on_sign_status("hands")

    def force_end(self):
        clip = self.seg.force_end()
        if clip:
            self._predict(clip)

    def _predict(self, clip):
        self.hub.on_sign_status("recognizing")
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(preprocess(np.array(clip)))[0]
        self.hub.on_sign_prediction(next(_seg_ids), topk(logits, self.glosses, self.vocab, k=5),
                                    latency_ms=round((time.perf_counter() - t0) * 1000))
        self.hub.on_sign_status("idle")


class NaturalEngine:
    name = "natural"

    def __init__(self, hub, signer, rest_line=0.85, background=True):
        self.hub, self.signer, self.rest_line = hub, signer, rest_line
        self.seg = SignSegmenter(start_frames=3, end_frames=21, preroll=8, postroll=9, min_frames=15, max_frames=300)
        self.background = background
        if background:
            self.jobs = queue.Queue()
            threading.Thread(target=self._worker, daemon=True, name="translate").start()

    def extract(self, frame_bgr):
        return self.signer.pose(frame_bgr)

    def landmarks(self, pose):
        k, s = pose
        hands = [_round(k[0, a:b]) for a, b in ((91, 112), (112, 133)) if s[0, a:b].mean() > 0.4]
        return {"hands": hands, "body": _round(k[0, [0, 5, 6, 7, 8, 9, 10]])}

    def on_pose(self, pose):
        active = hands_active_rtm(*pose, rest_line=self.rest_line)
        for ev in self.seg.push(pose, active):
            if ev[0] == "start":
                self.hub.on_sign_status("signing")
            elif ev[0] == "end":
                self._submit(ev[1])
            else:
                self.hub.on_sign_status("idle")
        if self.seg.state == "idle" and active:
            self.hub.on_sign_status("hands")

    def force_end(self):
        clip = self.seg.force_end()
        if clip:
            self._submit(clip)

    def _submit(self, clip):
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
        self.hub.on_sentence(out)
        self.hub.on_sign_status("idle")


class Vision:
    """Owns the camera. Runs the active engine on every frame and keeps the latest JPEG."""

    def __init__(self, hub, camera_index, engines, mode="natural"):
        self.hub, self.camera_index, self.engines, self.mode = hub, camera_index, engines, mode
        self.jpeg, self.fps = None, 0.0
        self.frame_ready = threading.Condition()
        self._force_end = False

    def set_mode(self, mode):
        self.mode = mode

    def force_end(self):
        self._force_end = True

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="vision").start()

    def _run(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if not cap.isOpened():
            self.hub.on_sign_status("no_camera")
            return
        engine, n, t0 = None, 0, time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok:
                self.hub.on_sign_status("no_camera")
                time.sleep(0.5)
                continue
            if engine is not self.engines[self.mode]:
                engine = self.engines[self.mode]
                engine.seg.force_end()  # drop any half-finished clip from the other mode
                self.hub.on_sign_status("idle")
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
