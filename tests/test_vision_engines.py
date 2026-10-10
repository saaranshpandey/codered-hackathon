import numpy as np
import torch


class HubStub:
    def __init__(self):
        self.statuses, self.predictions, self.sentences = [], [], []

    def on_sign_status(self, s):
        self.statuses.append(s)

    def on_sign_prediction(self, seg_id, topk, latency_ms=None):
        self.predictions.append((seg_id, topk))

    def on_sentence(self, result):
        self.sentences.append(result)


def holistic_pose(hand):
    a = np.zeros((543, 2))
    a[11] = (0.4, 0.5); a[12] = (0.6, 0.5)  # shoulders
    if hand:
        a[33:54] = 0.5
    return a


def test_hands_active_holistic():
    from medbridge.vision import hands_active_holistic

    assert hands_active_holistic(holistic_pose(False)) is False
    assert hands_active_holistic(holistic_pose(True)) is True


def rtm_pose(score, wrist_y):
    k = np.zeros((1, 133, 2)); s = np.zeros((1, 133))
    k[0, 91:112] = (0.5, wrist_y); s[0, 91:112] = score
    return k, s


def test_hands_active_rtm_requires_confident_hand_above_rest_line():
    from medbridge.vision import hands_active_rtm

    assert hands_active_rtm(*rtm_pose(0.9, 0.5), rest_line=0.85) is True
    assert hands_active_rtm(*rtm_pose(0.1, 0.5), rest_line=0.85) is False
    assert hands_active_rtm(*rtm_pose(0.9, 0.95), rest_line=0.85) is False


class FixedModel(torch.nn.Module):
    def forward(self, x):
        return torch.tensor([[0.0, 5.0, 0.0]])


def test_precise_engine_predicts_once_per_sign():
    from medbridge.vision import PreciseEngine

    hub = HubStub()
    eng = PreciseEngine(hub, FixedModel(), ["APPLE", "HURT", "ZEBRA"], {"HURT": "hurt", "APPLE": "apple"})
    for hand in [False] * 5 + [True] * 20 + [False] * 12:
        eng.on_pose(holistic_pose(hand))
    assert len(hub.predictions) == 1
    seg_id, topk = hub.predictions[0]
    assert topk[0]["label"] == "hurt"
    assert hub.statuses[-1] == "idle" and "signing" in hub.statuses


class FakeSigner:
    def translate(self, skeletons, confs):
        return {"candidates": [{"text": f"{len(confs)} frames", "score": -0.5, "rel_score": 1.0}], "latency_ms": 5}






class FakeCap:
    """Camera that produces a new 1080p frame every 5 ms; pixel [0,0,0] carries the frame number."""

    def __init__(self):
        self.i = 0

    def isOpened(self):
        return True

    def set(self, *a):
        pass

    def read(self):
        import time
        time.sleep(0.005)
        self.i += 1
        f = np.zeros((1080, 1920, 3), np.uint8)
        f[0, 0, 0] = self.i % 256
        return True, f


class SlowEngine:
    name = "natural"

    def __init__(self):
        from medbridge.segmenter import SignSegmenter
        self.seg = SignSegmenter()
        self.seen, self.shapes = [], []

    def extract(self, frame):
        import time
        time.sleep(0.03)
        self.shapes.append(frame.shape)
        return int(frame[0, 0, 0])

    def on_pose(self, pose):
        self.seen.append(pose)

    def landmarks(self, pose):
        return {"hands": [], "body": []}

    def force_end(self):
        pass

    def cancel(self):
        pass


class StreamHub(HubStub):
    def stream(self, msg):
        pass


def test_vision_processes_latest_frame_without_backlog_at_720p():
    import time

    from medbridge.vision import Vision

    eng = SlowEngine()
    v = Vision(StreamHub(), 0, {"natural": eng}, mode="natural", capture=lambda index: FakeCap())
    v.start()
    time.sleep(0.6)
    seen = eng.seen[:]
    assert len(seen) >= 8
    gaps = [b - a for a, b in zip(seen, seen[1:]) if b > a]
    assert max(gaps) > 1                      # stale frames were skipped, not queued
    assert set(eng.shapes) == {(720, 1280, 3)}



def test_natural_engine_ignores_signing_until_started():
    from medbridge.vision import NaturalEngine

    hub = HubStub()
    eng = NaturalEngine(hub, FakeSigner(), background=False)
    for k, s in [rtm_pose(0.9, 0.5)] * 60 + [rtm_pose(0.1, 0.5)] * 40:
        eng.on_pose((k, s))
    assert hub.sentences == []


def test_natural_engine_records_everything_between_start_and_done():
    from medbridge.vision import NaturalEngine

    hub = HubStub()
    eng = NaturalEngine(hub, FakeSigner(), background=False)
    eng.start()
    # hands low / undetected mid-sentence (e.g. STOMACH at belly height) must NOT end the recording
    for k, s in [rtm_pose(0.9, 0.5)] * 20 + [rtm_pose(0.1, 0.95)] * 40 + [rtm_pose(0.9, 0.5)] * 20:
        eng.on_pose((k, s))
    assert hub.sentences == [] and hub.statuses[-1] == "signing"
    eng.force_end()
    assert len(hub.sentences) == 1
    assert hub.sentences[0]["candidates"][0]["text"] == "80 frames"
    assert hub.statuses[-1] == "idle"


def test_natural_engine_discards_too_short_recording():
    from medbridge.vision import NaturalEngine

    hub = HubStub()
    eng = NaturalEngine(hub, FakeSigner(), background=False)
    eng.start()
    for k, s in [rtm_pose(0.9, 0.5)] * 5:
        eng.on_pose((k, s))
    eng.force_end()
    assert hub.sentences == [] and hub.statuses[-1] == "idle"


def test_natural_engine_stops_at_30_seconds():
    from medbridge.vision import NaturalEngine

    hub = HubStub()
    eng = NaturalEngine(hub, FakeSigner(), background=False)
    eng.start()
    for k, s in [rtm_pose(0.9, 0.5)] * 950:
        eng.on_pose((k, s))
    assert len(hub.sentences) == 1 and hub.sentences[0]["candidates"][0]["text"] == "900 frames"


def test_translating_status_is_kept_while_worker_runs():
    import threading

    from medbridge.vision import NaturalEngine

    release = threading.Event()

    class SlowSigner(FakeSigner):
        def translate(self, skeletons, confs):
            release.wait(5)
            return super().translate(skeletons, confs)

    hub = HubStub()
    eng = NaturalEngine(hub, SlowSigner(), background=True)
    eng.start()
    for k, s in [rtm_pose(0.9, 0.5)] * 30:
        eng.on_pose((k, s))
    eng.force_end()
    for k, s in [rtm_pose(0.9, 0.5)] * 10:
        eng.on_pose((k, s))
    assert hub.statuses[-1] == "translating"
    release.set()


def test_vision_start_signing_reaches_the_active_engine():
    import time

    from medbridge.vision import Vision

    eng = SlowEngine()
    eng.started = 0
    eng.start = lambda: setattr(eng, "started", eng.started + 1)
    v = Vision(StreamHub(), 0, {"natural": eng}, mode="natural", capture=lambda index: FakeCap())
    v.start()
    time.sleep(0.15)
    v.start_signing()
    time.sleep(0.2)
    assert eng.started == 1
