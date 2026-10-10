import numpy as np


class RecordingPipeline:
    def __init__(self):
        self.calls = []

    def feed(self, block, skip_interim=False):
        self.calls.append(skip_interim)


def test_interims_skipped_while_backlogged_then_resume():
    from medbridge.asr import MicAsr

    pipe = RecordingPipeline()
    mic = MicAsr(pipe, backlog_blocks=10)
    for _ in range(15):
        mic.queue.put(np.zeros(512, np.float32))
    for _ in range(15):
        mic.step()
    assert pipe.calls[:4] == [True] * 4
    assert pipe.calls[-5:] == [False] * 5


def test_paused_mic_drops_audio():
    from medbridge.asr import MicAsr

    pipe = RecordingPipeline()
    mic = MicAsr(pipe)
    mic.paused = True
    mic._callback(np.ones((512, 1), np.float32), 512, None, None)
    assert mic.queue.empty()
