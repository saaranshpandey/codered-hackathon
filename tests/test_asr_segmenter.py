import numpy as np

BLOCK = 512  # 32 ms at 16 kHz


def feed(seg, probs):
    events = []
    for i, p in enumerate(probs):
        block = np.full(BLOCK, i, dtype=np.float32)  # block i is filled with value i
        events += seg.push(block, p)
    return events


def make():
    from medbridge.asr import UtteranceSegmenter
    return UtteranceSegmenter(sr=16000, block=BLOCK, start_thr=0.5, end_silence_ms=600,
                              preroll_ms=200, max_ms=20000, interim_ms=700, min_speech_ms=250)


def test_final_emitted_after_trailing_silence():
    seg = make()
    events = feed(seg, [0.0] * 10 + [0.9] * 30 + [0.0] * 25)
    finals = [a for kind, a in events if kind == "final"]
    assert len(finals) == 1


def test_final_includes_preroll_blocks():
    seg = make()
    events = feed(seg, [0.0] * 10 + [0.9] * 30 + [0.0] * 25)
    audio = [a for kind, a in events if kind == "final"][0]
    first_block_value = audio[0]
    assert first_block_value == 10 - 6  # 200 ms preroll = 6 blocks before speech start at block 10


def test_interims_emitted_periodically_while_speaking():
    seg = make()
    events = feed(seg, [0.9] * 100)  # 3.2 s of speech, no end yet
    interims = [kind for kind, _ in events if kind == "interim"]
    assert 3 <= len(interims) <= 5


def test_final_forced_at_max_length():
    seg = make()
    events = feed(seg, [0.9] * 700)  # 22.4 s of continuous speech
    assert [kind for kind, _ in events].count("final") == 1


def test_short_blip_is_discarded():
    seg = make()
    events = feed(seg, [0.0] * 5 + [0.9] * 3 + [0.0] * 30)  # ~96 ms of "speech"
    assert [kind for kind, _ in events if kind == "final"] == []
