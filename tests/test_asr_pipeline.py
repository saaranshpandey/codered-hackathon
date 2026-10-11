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


def at_level(audio, dbfs):
    """The same audio, scaled so that its RMS level is `dbfs` (decibels relative to full scale)."""
    return (audio * 10 ** (dbfs / 20) / np.sqrt(np.mean(audio ** 2))).astype(np.float32)


def run_stream(transcriber, audio, gate_db=None):
    """Events (kind, utt_id, text, sample position in the stream when the event came). The stream starts with 0.5 s
    of silence."""
    from medbridge.asr import SpeechPipeline

    events, pos = [], [0]
    pipe = SpeechPipeline(transcriber, lambda kind, utt_id, text: events.append((kind, utt_id, text, pos[0])),
                          gate_db=gate_db)
    stream = np.concatenate([np.zeros(8000, np.float32), audio, np.zeros(16000, np.float32)])
    for i in range(0, len(stream) - 511, 512):
        pos[0] = i + 512
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


# Loudness gate (MIC_GATE). The doctor is near the mic (-20 dBFS); talk across the room reaches it at about -55 dBFS.

def test_quiet_speech_is_still_captioned_without_the_gate(tmp_path, transcriber):
    events = run_stream(transcriber, at_level(tts(tmp_path, "Are you experiencing chest pain?"), -55))
    assert any(e[0] == "final" for e in events)


def test_gate_drops_speech_quieter_than_the_gate(tmp_path, transcriber):
    events = run_stream(transcriber, at_level(tts(tmp_path, "Are you experiencing chest pain?"), -55), gate_db=-40)
    assert [e for e in events if e[0] in ("interim", "final")] == []


def test_gate_keeps_speech_louder_than_the_gate(tmp_path, transcriber):
    events = run_stream(transcriber, at_level(tts(tmp_path, "Are you experiencing chest pain?"), -20), gate_db=-40)
    finals = [e for e in events if e[0] == "final"]
    assert len(finals) == 1
    assert "chest pain" in finals[0][2].lower()


def test_quiet_background_talk_does_not_hold_the_caption_open(tmp_path, transcriber):
    doctor = at_level(tts(tmp_path, "Are you experiencing chest pain?"), -20)
    room = at_level(tts(tmp_path, "The patient in bed four needs a blanket and some water, and the printer is jammed again."), -55)
    events = run_stream(transcriber, np.concatenate([doctor, room]), gate_db=-40)
    finals = [e for e in events if e[0] == "final"]
    assert len(finals) == 1
    assert "chest pain" in finals[0][2].lower()
    # The caption closes about 0.6 s after the doctor stops, not when the room goes quiet several seconds later.
    assert finals[0][3] < 8000 + len(doctor) + 16000
