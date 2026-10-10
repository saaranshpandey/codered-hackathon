"""Cuts a live per-frame stream into sign clips using hand presence.

Precise mode uses it per sign, natural mode per sentence (longer end_frames: the patient
rests their hands to finish). push() returns events: ("start",), ("end", clip), ("discard",)."""
import collections


class SignSegmenter:
    def __init__(self, start_frames=3, end_frames=10, preroll=8, postroll=8, min_frames=12, max_frames=128):
        self.start_frames, self.end_frames = start_frames, end_frames
        self.preroll, self.postroll = preroll, postroll
        self.min_frames, self.max_frames = min_frames, max_frames
        self.history = collections.deque(maxlen=preroll + start_frames)
        self.run = 0
        self.clip = None
        self.miss = 0

    @property
    def state(self):
        return "idle" if self.clip is None else "signing"

    def push(self, item, hands):
        if self.clip is None:
            self.history.append(item)
            self.run = self.run + 1 if hands else 0
            if self.run >= self.start_frames:
                self.clip = list(self.history)[-(self.preroll + self.run):]
                self.miss = 0
                return [("start",)]
            return []

        self.clip.append(item)
        self.miss = 0 if hands else self.miss + 1
        if self.miss >= self.end_frames or len(self.clip) >= self.max_frames:
            clip = self._finish()
            return [("end", clip)] if clip else [("discard",)]
        return []

    def force_end(self):
        """Manual "done signing": returns the clip so far (or None when idle/too short)."""
        if self.clip is None:
            return None
        return self._finish()

    def _finish(self):
        clip = self.clip[: len(self.clip) - max(0, self.miss - self.postroll)]
        self.clip, self.run, self.miss = None, 0, 0
        self.history.clear()
        return clip if len(clip) >= self.min_frames else None
