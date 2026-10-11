"""Doctor's words -> signing motion for the patient's 3D figure.

Word-by-word: each word is mapped to an ASL Citizen sign and played with the motion of a Deaf signer
from that dataset (MediaPipe landmarks, local cache). Words without a local sign are fetched from sign.mt
(text -> pose, often fingerspelled) if enabled; otherwise they are shown as text.
This is not ASL grammar.

Speed: a sign that is not cached yet costs seconds (one video download plus pose tracking on every frame),
so signs are looked up side by side on a small thread pool, started early from interim captions, kept in
memory once built, and long texts are handed out in batches so signing starts before the last word is ready.

Motion layout (shared with sign.mt's pose files): 178 points x (x, y, z)
  0-7    body: L/R shoulder, L/R elbow, L/R wrist, L/R hip   (person's left/right)
  8-135  face: 128 MediaPipe face-mesh points (FACE_IDX)
  136-156 left hand (21)     157-177 right hand (21)
Missing points are NaN.
"""
import base64
import collections
import concurrent.futures
import contextlib
import csv
import importlib.util
import logging
import os
import re
import tempfile
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

FACE_IDX = [0, 7, 10, 13, 14, 17, 21, 33, 37, 39, 40, 46, 52, 53, 54, 55, 58, 61, 63, 65, 66, 67, 70, 78, 80, 81, 82, 84,
            87, 88, 91, 93, 95, 103, 105, 107, 109, 127, 132, 133, 136, 144, 145, 146, 148, 149, 150, 152, 153, 154, 155,
            157, 158, 159, 160, 161, 162, 163, 172, 173, 176, 178, 181, 185, 191, 234, 246, 249, 251, 263, 267, 269, 270,
            276, 282, 283, 284, 285, 288, 291, 293, 295, 296, 297, 300, 308, 310, 311, 312, 314, 317, 318, 321, 323, 324,
            332, 334, 336, 338, 356, 361, 362, 365, 373, 374, 375, 377, 378, 379, 380, 381, 382, 384, 385, 386, 387, 388,
            389, 390, 397, 398, 400, 402, 405, 409, 415, 454, 466]
BODY_IDX = [11, 12, 13, 14, 15, 16, 23, 24]  # MediaPipe pose indices for the 8 body points
N_POINTS = 178
LH, RH = 136, 157

# Words that ASL usually leaves unsigned (articles, copulas, auxiliaries, filler).
UNSIGNED = {"a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "being", "to", "of", "do", "does", "did",
            "it", "its", "it's", "that", "this", "there's", "some", "any", "just", "so", "very", "um", "uh", "oh",
            "and", "for", "at", "on", "in", "as", "such", "by", "with"}
SYNONYMS = {"i": "me", "i'm": "me", "im": "me", "i've": "me", "i'll": "me", "mine": "my", "you're": "you", "hi": "hello",
            "hey": "hello", "okay": "ok", "she": "he", "her": "he", "him": "he", "experiencing": "feel", "feeling": "feel",
            "medication": "medicine", "medications": "medicine", "meds": "medicine", "don't": "not", "doesn't": "not",
            "didn't": "not", "can't": "cannot", "won't": "not", "what's": "what", "where's": "where", "aching": "hurt",
            "ache": "hurt", "pains": "pain", "hurting": "hurt"}
BIGRAMS = {("thank", "you"): "thankyou", ("thank", "u"): "thankyou"}
NUMBERS = {str(i): w for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"])}


def _key(gloss):
    return re.sub(r"[^a-z]", "", re.sub(r"\d+$", "", gloss.lower()))


def build_lexicon(glosses):
    """English key -> gloss, preferring plain variants: not fingerspelled (W.H.A.T), not number-prefixed
    (8HOUR is "eight hours"), then the lowest-numbered variant (DOCTOR1)."""
    lex = {}
    for g in sorted(glosses, key=lambda g: ("." in g, g[:1].isdigit(), g)):
        lex.setdefault(_key(g), g)
    return lex


def _lookup(word, lex):
    w = SYNONYMS.get(word, NUMBERS.get(word, word))
    w = SYNONYMS.get(w, w)
    for cand in (w, w[:-1] if w.endswith("s") else None, w[:-2] if w.endswith("es") else None,
                 w[:-3] + "y" if w.endswith("ies") else None, w[:-3] if w.endswith("ing") else None,
                 w[:-2] if w.endswith("ed") else None, w[:-1] if w.endswith("ed") else None):
        if cand and re.sub(r"[^a-z]", "", cand) in lex:
            return lex[re.sub(r"[^a-z]", "", cand)]
    return None


def text_to_glosses(text, lex):
    """[(word, gloss or None)] in English word order, skipping words ASL leaves unsigned."""
    words = re.findall(r"[a-z0-9']+", text.lower())
    out, i = [], 0
    while i < len(words):
        if i + 1 < len(words) and (words[i], words[i + 1]) in BIGRAMS:
            key = BIGRAMS[(words[i], words[i + 1])]
            out.append((f"{words[i]} {words[i + 1]}", lex.get(key)))
            i += 2
            continue
        w = words[i].strip("'")
        if w and w not in UNSIGNED:
            out.append((w, _lookup(w, lex)))
        i += 1
    return out


def holistic_frame(results, width, height):
    """MediaPipe Holistic result -> (178, 3) pixels; hand z is made absolute using the body wrist depth."""
    f = np.full((N_POINTS, 3), np.nan, np.float32)

    def put(start, lms, idx=None, z0=0.0):
        pts = lms.landmark if idx is None else [lms.landmark[i] for i in idx]
        f[start:start + len(pts)] = [(p.x * width, p.y * height, (p.z + z0) * width) for p in pts]

    if results.pose_landmarks:
        put(0, results.pose_landmarks, BODY_IDX)
    if results.face_landmarks:
        put(8, results.face_landmarks, FACE_IDX)
    pose = results.pose_landmarks
    if results.left_hand_landmarks:
        put(LH, results.left_hand_landmarks, z0=pose.landmark[15].z if pose else 0.0)
    if results.right_hand_landmarks:
        put(RH, results.right_hand_landmarks, z0=pose.landmark[16].z if pose else 0.0)
    return f


def normalize(seq):
    """Centre on the mean shoulder midpoint and scale so the mean shoulder width is 1."""
    ls, rs = seq[:, 0], seq[:, 1]
    centre = np.nanmean((ls + rs) / 2, axis=0)
    width = np.nanmean(np.linalg.norm((ls - rs)[:, :2], axis=1))
    if not np.isfinite(width) or width == 0:
        return seq
    return ((seq - centre) / width).astype(np.float32)


def resample(seq, fps_in, fps_out=30):
    n = len(seq)
    if n < 2 or fps_in == fps_out:
        return seq
    t_in = np.arange(n) / fps_in
    t_out = np.arange(int(round((n - 1) / fps_in * fps_out)) + 1) / fps_out
    flat = seq.reshape(n, -1)
    out = np.stack([np.interp(t_out, t_in, flat[:, j]) for j in range(flat.shape[1])], axis=1)
    return out.reshape(len(t_out), *seq.shape[1:]).astype(np.float32)


def fill_gaps(seq, max_gap=8):
    """Linearly fill short runs of missing frames per point (tracking dropouts mid-sign), so hands
    don't flicker out; longer gaps and leading/trailing absences stay missing."""
    out = seq.copy()
    missing = np.isnan(seq[..., 0])
    for p in np.where(missing.any(axis=0) & ~missing.all(axis=0))[0]:
        idx = np.where(~missing[:, p])[0]
        for a, b in zip(idx[:-1], idx[1:]):
            if 1 < b - a <= max_gap + 1:
                t = (np.arange(a + 1, b) - a) / (b - a)
                out[a + 1:b, p] = seq[a, p] + (seq[b, p] - seq[a, p]) * t[:, None]
    return out


def trim_to_hands(seq, pad=3):
    present = ~np.isnan(seq[:, LH:, 0]).all(axis=1)
    idx = np.where(present)[0]
    return seq[max(0, idx[0] - pad): idx[-1] + 1 + pad] if len(idx) else seq


def hand_coverage(seq, min_frames=8):
    """Share of frames with a tracked hand, counted from the first such frame to the last. Signers rest their
    hands before and after a sign, so the share over the whole clip is low even when tracking is perfect."""
    present = ~np.isnan(seq[:, LH:, 0]).all(axis=1)
    idx = np.where(present)[0]
    return float(present[idx[0]:idx[-1] + 1].mean()) if len(idx) >= min_frames else 0.0


def _blend(a, b, t):
    a2 = np.where(np.isnan(a), b, a)
    b2 = np.where(np.isnan(b), a, b)
    return a2 + (b2 - a2) * t


def assemble(segments, fps=30, transition=8, hold=18, prev=None, offset=0):
    """segments: [(word, gloss, source, seq or None)] -> (motion (N, 178, 3), timeline).
    Signs are joined with eased transitions; words without motion hold the last pose briefly.
    To continue an earlier batch, pass its last frame as `prev` and its frame count so far as `offset`:
    the motion returned is only the new frames, and the timeline keeps counting from `offset`."""
    frames, timeline = [], []
    empty = np.full((N_POINTS, 3), np.nan, np.float32)
    last = prev
    for word, gloss, source, seq in segments:
        if seq is None:
            seq = np.repeat((last if last is not None else empty)[None], hold, axis=0)
        if last is not None and transition:
            first = seq[0]
            for k in range(1, transition + 1):
                t = k / (transition + 1)
                frames.append(_blend(last, first, t * t * (3 - 2 * t)))
        start = len(frames)
        frames.extend(seq)
        last = frames[-1]
        timeline.append({"word": word, "gloss": gloss, "source": source, "start": offset + start, "end": offset + len(frames)})
    motion = np.array(frames, np.float32) if frames else np.zeros((0, N_POINTS, 3), np.float32)
    return motion, timeline


def payload(caption_id, motion, timeline, fps=30):
    return {"caption_id": caption_id, "fps": fps, "frames": int(len(motion)), "points": N_POINTS, "words": timeline,
            "data": base64.b64encode(np.ascontiguousarray(motion, np.float32).tobytes()).decode()}


class AslCitizenSigns:
    """gloss -> Deaf signer's motion (pixels, 30 fps), from ASL Citizen videos; cached under data/signlex/aslc."""
    ZIP = "https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"

    def __init__(self, root):
        self.root = Path(root)
        self.cache = self.root / "data/signlex/aslc"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.videos = {}
        with open(self.root / "data/aslc/ASL_Citizen/splits/train.csv") as f:
            for row in list(csv.reader(f))[1:]:
                self.videos.setdefault(row[2].strip(), []).append(row[1])
        self._zip = None
        self._zip_lock = threading.Lock()  # one shared zip: its index is read once, downloads take turns (they are short)
        self._locks = {}
        self.lock = threading.Lock()

    def connect(self):
        """Read the dataset zip's index (about a second) ahead of the first download."""
        self._download(None)

    def _download(self, name):
        from remotezip import RemoteZip

        with self._zip_lock:
            try:
                if self._zip is None:
                    self._zip = RemoteZip(self.ZIP)
                return self._zip.read(f"ASL_Citizen/videos/{name}") if name else None
            except Exception:
                self._zip = None
                raise

    def has(self, gloss):
        return (self.cache / f"{gloss}.npy").exists()

    def get(self, gloss):
        """Thread-safe. Different signs are built side by side; one sign is never built twice at once."""
        path = self.cache / f"{gloss}.npy"
        if path.exists():
            return np.load(path)
        with self.lock:
            building = self._locks.setdefault(gloss, threading.Lock())
        with building:
            if path.exists():
                return np.load(path)
            seq = self._build(gloss)
            if seq is not None:  # write to a temp file first, so no other thread loads a half-written sign
                fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=self.cache)
                with os.fdopen(fd, "wb") as f:
                    np.save(f, seq)
                os.replace(tmp, path)
        return seq

    @contextlib.contextmanager
    def _temp_clip(self):
        """A private temp file per download, so parallel builders never overwrite each other's video."""
        fd, name = tempfile.mkstemp(suffix=".mp4", dir=self.cache)
        os.close(fd)
        path = Path(name)
        try:
            yield path
        finally:
            path.unlink(missing_ok=True)

    def _build(self, gloss):
        import cv2
        import mediapipe as mp

        best, best_score = None, -1.0
        for name in self.videos.get(gloss, [])[:3]:
            try:
                data = self._download(name)
            except Exception as e:  # network or zip error: try the next clip
                log.warning("ASL Citizen fetch failed for %s: %s", gloss, e)
                continue
            frames = []
            with self._temp_clip() as tmp:
                tmp.write_bytes(data)
                cap = cv2.VideoCapture(str(tmp))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                with mp.solutions.holistic.Holistic(static_image_mode=False, min_detection_confidence=0.5) as h:
                    while True:
                        ok, img = cap.read()
                        if not ok:
                            break
                        frames.append(holistic_frame(h.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), img.shape[1], img.shape[0]))
                cap.release()
            if not frames:
                continue
            seq = np.array(frames)
            score = hand_coverage(seq)
            if score > best_score:
                best, best_score = resample(trim_to_hands(seq), fps, 30), score
            if best_score >= 0.8:  # hands tracked through the sign: good enough, the other clips are not needed
                break
        return best


class SignMT:
    """word -> (motion, fps) from the open sign.mt text-to-pose service; cached under data/signlex/signmt.
    Only words missing from the local dictionary are sent."""
    URL = "https://us-central1-sign-mt.cloudfunctions.net/spoken_text_to_signed_pose"

    def __init__(self, root, timeout=8):
        self.cache = Path(root) / "data/signlex/signmt"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.available = importlib.util.find_spec("pose_format") is not None
        if not self.available:
            log.warning("pose_format is not installed: words without a local sign are shown as text only")

    def get(self, word):
        safe = re.sub(r"[^a-z0-9]", "_", word.lower())
        path = self.cache / f"{safe}.npz"
        if path.exists():
            z = np.load(path)
            return z["seq"], float(z["fps"])
        if not self.available:
            return None
        try:
            from pose_format import Pose

            q = urllib.parse.urlencode({"text": word, "spoken": "en", "signed": "ase"})
            with urllib.request.urlopen(f"{self.URL}?{q}", timeout=self.timeout) as r:
                pose = Pose.read(r.read())
        except Exception as e:
            log.warning("sign.mt unavailable for %r: %s", word, e)
            return None
        data = np.array(pose.body.data[:, 0], np.float32)
        conf = np.array(pose.body.confidence[:, 0])
        data[conf <= 0] = np.nan
        np.savez(path, seq=data, fps=pose.body.fps)
        return data, float(pose.body.fps)


class Builder:
    """Text -> signing motion. Thread-safe: signs are looked up on a thread pool and kept in memory."""

    def __init__(self, lexicon, local, signmt=None, workers=4, keep=400):
        self.lexicon, self.local, self.signmt = lexicon, local, signmt
        self.pool = concurrent.futures.ThreadPoolExecutor(workers, thread_name_prefix="signs")
        self.keep = keep
        self.lock = threading.Lock()
        self.ready = collections.OrderedDict()  # ("aslc", gloss) | ("signmt", word) -> motion, ready to join
        self.inflight = {}                      # same keys -> Future, for lookups that are running

    def _lookup(self, word, gloss):
        """Future of (source, motion or None): the local sign for `gloss`, or sign.mt for a word without one."""
        key = ("aslc", gloss) if gloss else ("signmt", word)
        with self.lock:
            if key in self.ready:
                self.ready.move_to_end(key)
                done = concurrent.futures.Future()
                done.set_result((key[0], self.ready[key]))
                return done
            if not gloss and self.signmt is None:
                done = concurrent.futures.Future()
                done.set_result(("none", None))
                return done
            if key not in self.inflight:
                self.inflight[key] = self.pool.submit(self._work, key)
            return self.inflight[key]

    def _work(self, key):
        kind, name = key
        try:
            if kind == "aslc":
                seq = self.local.get(name)
            else:
                got = self.signmt.get(name)
                seq = resample(got[0], got[1], 30) if got else None
            if seq is None or not len(seq):  # not kept, so a failed download is tried again next time
                return "none", None
            seq = fill_gaps(normalize(seq))
            with self.lock:
                self.ready[key] = seq
                while len(self.ready) > self.keep:
                    self.ready.popitem(last=False)
            return kind, seq
        finally:
            with self.lock:
                self.inflight.pop(key, None)

    def warm(self):
        """Do the one-off connection work now, in the background, instead of on the first new word."""
        connect = getattr(self.local, "connect", None)
        if connect:
            self.pool.submit(connect).add_done_callback(
                lambda f: f.exception() and log.warning("sign dictionary not reachable yet: %s", f.exception()))

    def prefetch(self, text):
        """Start fetching the local signs for words that are probably coming (an interim caption), without
        waiting. Unfinished text is never sent to sign.mt."""
        has = getattr(self.local, "has", None)
        for word, gloss in text_to_glosses(text, self.lexicon):
            if gloss and not (has and has(gloss)):
                self._lookup(word, gloss)

    def stream(self, text, batch=12, patience=0.05, max_wait=8.0):
        """Yield (motion, timeline) batches in word order; timeline frame numbers count from the start of the text.
        A batch closes at `batch` words, or when the next word is not ready within `patience` seconds, so signs
        that are ready are never held back by a slow one. A sign still not ready `max_wait` seconds after it is
        needed is left out this time (shown as text); it keeps building and is there the next time."""
        lookups = [(word, gloss, self._lookup(word, gloss)) for word, gloss in text_to_glosses(text, self.lexicon)]
        segments, last, offset = [], None, 0

        def flush():
            nonlocal segments, last, offset
            motion, timeline = assemble(segments, prev=last, offset=offset)
            segments, last, offset = [], motion[-1], offset + len(motion)
            return motion, timeline

        for word, gloss, lookup in lookups:
            if segments:
                try:
                    lookup.result(timeout=patience)
                except concurrent.futures.TimeoutError:
                    yield flush()
            try:
                source, seq = lookup.result(timeout=max_wait)
            except concurrent.futures.TimeoutError:
                source, seq = "none", None
            if seq is None and gloss and self.signmt is not None and lookup.done():  # the local sign could not be fetched
                source, seq = self._lookup(word, None).result()
            segments.append((word, gloss, source, seq))
            if len(segments) >= batch:
                yield flush()
        if segments:
            yield flush()

    def build(self, text):
        """The whole text in one piece: (motion, timeline)."""
        parts = list(self.stream(text, batch=10 ** 9, patience=None, max_wait=None))
        return parts[0] if parts else assemble([])
