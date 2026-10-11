"""Pausing captions throws away what was being said; resuming starts from silence."""
import numpy as np

BLOCK = 512  # 32 ms at 16 kHz


class LoudIsSpeech:
    """A voice detector stand-in: a block counts as speech when it is not silent."""
    resets = 0

    def __call__(self, block, sr):
        return block.abs().max()

    def reset_states(self):
        self.resets += 1


def make_pipeline(transcriber, events):
    from medbridge.asr import SpeechPipeline

    pipe = SpeechPipeline(transcriber, lambda kind, utt, text: events.append((kind, text)))
    pipe.vad = LoudIsSpeech()
    return pipe


def test_reset_drops_the_utterance_in_progress():
    heard, events = [], []

    def transcriber(audio):
        heard.append(audio)
        return "words"

    pipe = make_pipeline(transcriber, events)
    for _ in range(15):  # half a second of speech, then the doctor pauses mid-sentence
        pipe.feed(np.full(BLOCK, 0.9, np.float32))
    pipe.reset()
    assert pipe.in_speech is False
    for _ in range(15):  # resumed: a new sentence, then silence
        pipe.feed(np.full(BLOCK, 0.6, np.float32))
    for _ in range(25):
        pipe.feed(np.zeros(BLOCK, np.float32))

    assert [kind for kind, _ in events][-1] == "final"
    assert {float(audio.max()) for audio in heard} == {float(np.float32(0.6))}  # nothing from before the reset
    assert pipe.vad.resets == 1


def test_reset_while_transcribing_drops_that_caption():
    events = []

    def transcriber(audio):
        pipe.reset()  # the doctor pauses while the model is still working
        return "old words"

    pipe = make_pipeline(transcriber, events)
    for _ in range(15):
        pipe.feed(np.full(BLOCK, 0.9, np.float32))
    for _ in range(25):
        pipe.feed(np.zeros(BLOCK, np.float32))
    assert events == []


def test_segmenter_reset_forgets_speech_and_preroll():
    from medbridge.asr import UtteranceSegmenter

    seg = UtteranceSegmenter()
    seg.push(np.zeros(BLOCK, np.float32), 0.0)
    seg.push(np.ones(BLOCK, np.float32), 0.9)
    seg.reset()
    assert seg.buf is None and len(seg.preroll) == 0


class CountingPipeline:
    resets = 0

    def reset(self):
        self.resets += 1


def test_pausing_and_resuming_the_mic_clear_what_was_waiting():
    from medbridge.asr import MicAsr

    pipe = CountingPipeline()
    mic = MicAsr(pipe)
    for _ in range(5):
        mic.queue.put(np.zeros(BLOCK, np.float32))

    mic.set_paused(True)
    assert mic.paused and mic.queue.empty() and pipe.resets == 1
    mic._callback(np.ones((BLOCK, 1), np.float32), BLOCK, None, None)
    assert mic.queue.empty()

    mic.queue.put(np.zeros(BLOCK, np.float32))  # a block that slipped in while pausing
    mic.set_paused(False)
    assert not mic.paused and mic.queue.empty() and pipe.resets == 2
    mic._callback(np.ones((BLOCK, 1), np.float32), BLOCK, None, None)
    assert mic.queue.qsize() == 1
