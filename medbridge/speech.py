"""The patient's confirmed message, spoken aloud for the doctor through the ElevenLabs text-to-speech API.

Off unless ELEVENLABS_API_KEY is set. When it is on, the text of each confirmed patient message is sent to
ElevenLabs. The audio is kept in memory only."""
import json
import logging
import os
import threading
import urllib.request

log = logging.getLogger(__name__)

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
BITRATE = 128_000  # bits per second of the mp3 asked for above
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George", the voice in the ElevenLabs quickstart
DEFAULT_MODEL = "eleven_flash_v2_5"     # their lowest-latency model


def seconds(audio):
    """How long an mp3 from speak() plays."""
    return len(audio) * 8 / BITRATE


class ElevenLabsVoice:
    def __init__(self, api_key, voice=DEFAULT_VOICE, model=DEFAULT_MODEL, timeout=10):
        self.api_key, self.voice, self.model, self.timeout = api_key, voice, model, timeout

    def speak(self, text):
        """text -> mp3 bytes. Raises on a network error or a refusal from the service (bad key, quota)."""
        request = urllib.request.Request(
            URL.format(voice=self.voice), data=json.dumps({"text": text, "model_id": self.model}).encode(),
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()


def make_voice():
    """The voice configured in the environment, or None when no key is set."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return None
    return ElevenLabsVoice(key, os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE,
                           os.environ.get("ELEVENLABS_MODEL", "").strip() or DEFAULT_MODEL)


class Speaker:
    """Audio for confirmed patient messages: made once per message, on the first request, and kept in memory."""

    def __init__(self, hub, voice, keep=50):
        self.hub, self.voice, self.keep = hub, voice, keep
        self.audio = {}
        self.making = {}
        self.lock = threading.Lock()

    def get(self, message_id):
        """mp3 bytes for a confirmed message, or None if there is no such message."""
        with self.hub.lock:
            text = next((m["text"] for m in self.hub.state["messages"] if m["id"] == message_id), None)
        if text is None:
            return None
        with self.lock:
            making = self.making.setdefault(message_id, threading.Lock())
        with making:  # two doctor tabs asking at once make one request, not two
            audio = self.audio.get(message_id)
            if audio is None:
                audio = self.voice.speak(text)
                with self.lock:
                    self.audio[message_id] = audio
                    for old in sorted(self.audio)[:-self.keep]:
                        del self.audio[old]
                        self.making.pop(old, None)
            return audio
