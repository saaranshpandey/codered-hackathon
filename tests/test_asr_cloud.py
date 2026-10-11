import json

import numpy as np


class OneUtterance:
    """A segmenter stand-in: the first block yields an interim and then the final for one utterance."""
    buf = None

    def __init__(self, audio):
        self.events = [("interim", audio), ("final", audio)]

    def push(self, block, prob):
        out, self.events = self.events, []
        return out


def run(final_transcriber):
    from medbridge.asr import SpeechPipeline

    events = []
    pipe = SpeechPipeline(lambda audio: "local text", lambda kind, utt, text: events.append((kind, text)),
                          segmenter=OneUtterance(np.zeros(8000, np.float32)), final_transcriber=final_transcriber)
    pipe.feed(np.zeros(512, np.float32))
    return events


def test_cloud_engine_writes_the_final_text_and_the_local_model_the_live_text():
    assert run(lambda audio: "cloud text") == [("interim", "local text"), ("final", "cloud text")]
    assert run(None) == [("interim", "local text"), ("final", "local text")]


def test_local_model_takes_over_when_the_cloud_call_fails():
    def broken(audio):
        raise OSError("network is down")

    assert run(broken) == [("interim", "local text"), ("final", "local text")]


def test_elevenlabs_speech_to_text_request(monkeypatch):
    import urllib.request

    from medbridge.asr import ElevenLabsTranscriber

    seen = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"text": "  Are you allergic to penicillin?  ", "words": []}).encode()

    def urlopen(request, timeout):
        seen.update(url=request.full_url, headers={k.lower(): v for k, v in request.header_items()}, body=request.data, timeout=timeout)
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    audio = np.array([0.0, 0.5, -0.5, 2.0], np.float32)          # 2.0 is clipped to full scale
    text = ElevenLabsTranscriber("secret-key", keyterms=["penicillin", "CT scan"], timeout=5)(audio)
    assert text == "Are you allergic to penicillin?"
    assert seen["url"] == "https://api.elevenlabs.io/v1/speech-to-text" and seen["timeout"] == 5
    assert seen["headers"]["xi-api-key"] == "secret-key"
    boundary = seen["headers"]["content-type"].split("boundary=")[1]
    parts = seen["body"].split(f"--{boundary}".encode())
    fields = [(p.split(b'name="')[1].split(b'"')[0].decode(), p.split(b"\r\n\r\n", 1)[1][:-2]) for p in parts[1:-1]]
    assert fields[:4] == [("model_id", b"scribe_v2"), ("file_format", b"pcm_s16le_16"), ("language_code", b"en"),
                          ("tag_audio_events", b"false")]
    assert [v for k, v in fields if k == "keyterms"] == [b"penicillin", b"CT scan"]
    assert dict(fields)["file"] == np.array([0, 16383, -16383, 32767], "<i2").tobytes()
