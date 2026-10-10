import shutil
import subprocess
import wave

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(shutil.which("say") is None, reason="needs macOS `say` for test speech")


def tts(tmp_path, text):
    path = tmp_path / "speech.wav"
    subprocess.run(["say", "-o", str(path), "--file-format=WAVE", "--data-format=LEI16@16000", text], check=True)
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


@pytest.fixture(scope="module")
def transcriber():
    from medbridge.asr import Transcriber
    return Transcriber()


def run_stream(transcriber, audio):
    from medbridge.asr import SpeechPipeline

    events = []
    pipe = SpeechPipeline(transcriber, lambda kind, utt_id, text: events.append((kind, utt_id, text)))
    stream = np.concatenate([np.zeros(8000, np.float32), audio, np.zeros(16000, np.float32)])
    for i in range(0, len(stream) - 511, 512):
        pipe.feed(stream[i:i + 512])
    return events


def test_spoken_question_becomes_one_final_caption(tmp_path, transcriber):
    events = run_stream(transcriber, tts(tmp_path, "Are you experiencing chest pain?"))
    finals = [e for e in events if e[0] == "final"]
    assert len(finals) == 1
    assert "chest pain" in finals[0][2].lower()


def test_interims_share_the_final_utterance_id(tmp_path, transcriber):
    events = run_stream(transcriber, tts(tmp_path, "Please tell me when the pain started and whether it spreads to your left arm."))
    ids = {e[1] for e in events if e[0] in ("interim", "final")}
    assert any(e[0] == "interim" for e in events)
    assert len(ids) == 1


def test_silence_produces_no_caption(transcriber):
    events = run_stream(transcriber, np.zeros(16000 * 2, np.float32))
    assert [e for e in events if e[0] in ("interim", "final")] == []
