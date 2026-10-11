import json

import pytest


def test_elevenlabs_request_carries_the_key_voice_model_and_text(monkeypatch):
    import urllib.request

    from medbridge.speech import ElevenLabsVoice

    seen = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"mp3-bytes"

    def urlopen(request, timeout):
        seen.update(url=request.full_url, headers={k.lower(): v for k, v in request.header_items()},
                    body=json.loads(request.data), method=request.get_method(), timeout=timeout)
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    audio = ElevenLabsVoice("secret-key", voice="VOICE1", model="eleven_flash_v2_5", timeout=7).speak("Heart hurt.")
    assert audio == b"mp3-bytes"
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/VOICE1?output_format=mp3_44100_128"
    assert seen["method"] == "POST" and seen["timeout"] == 7
    assert seen["headers"]["xi-api-key"] == "secret-key"
    assert seen["body"] == {"text": "Heart hurt.", "model_id": "eleven_flash_v2_5"}


def test_voice_is_off_without_a_key_and_reads_its_settings_from_the_environment(monkeypatch):
    from medbridge.speech import DEFAULT_MODEL, DEFAULT_VOICE, make_voice

    for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert make_voice() is None
    monkeypatch.setenv("ELEVENLABS_API_KEY", "  ")
    assert make_voice() is None
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    v = make_voice()
    assert (v.api_key, v.voice, v.model) == ("k", DEFAULT_VOICE, DEFAULT_MODEL)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "abc")
    monkeypatch.setenv("ELEVENLABS_MODEL", "eleven_v4_turbo")
    v = make_voice()
    assert (v.voice, v.model) == ("abc", "eleven_v4_turbo")


def test_clip_length_is_estimated_from_its_size():
    from medbridge.speech import seconds

    assert seconds(b"x" * 32_000) == pytest.approx(2.0)   # 128 kbit/s mp3
