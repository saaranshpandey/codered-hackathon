"""Doctor speech -> live captions: Silero VAD segments utterances, mlx-whisper transcribes them.
Audio stays in memory and is dropped after transcription.

With ASR_ENGINE=elevenlabs, the final text of each utterance comes from ElevenLabs Scribe instead (the
utterance's audio is sent to ElevenLabs); Whisper still gives the live text while the doctor is speaking,
and takes over for any utterance the cloud call fails on."""
import collections
import json
import logging
import time
import urllib.request
import uuid

import numpy as np

from medbridge import metrics

log = logging.getLogger(__name__)

WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
# Biases spelling toward ER vocabulary; it is a decoding hint, not inserted text.
ER_PROMPT = ("Emergency department conversation. Chest pain, shortness of breath, nausea, dizziness, "
             "allergies, penicillin, ibuprofen, acetaminophen, aspirin, nitroglycerin, blood pressure, CT scan, IV.")


class Transcriber:
    def __init__(self, repo=WHISPER_REPO, prompt=ER_PROMPT):
        import mlx_whisper

        self._transcribe = mlx_whisper.transcribe
        self.repo, self.prompt = repo, prompt
        self(np.zeros(16000, np.float32))  # load + warm up

    def __call__(self, audio):
        out = self._transcribe(audio, path_or_hf_repo=self.repo, language="en", initial_prompt=self.prompt,
                               condition_on_previous_text=False, verbose=None)
        segs = out.get("segments", [])
        if not segs or all(s.get("no_speech_prob", 0) > 0.6 for s in segs):
            return ""
        return out["text"].strip()


# Words Scribe is told to listen for (its counterpart of ER_PROMPT). ElevenLabs bills 20% more when any are sent.
ER_TERMS = ["chest pain", "shortness of breath", "nausea", "dizziness", "allergies", "penicillin", "ibuprofen",
            "acetaminophen", "aspirin", "nitroglycerin", "blood pressure", "blood thinners", "CT scan", "IV"]


class ElevenLabsTranscriber:
    """Cloud speech-to-text: 16 kHz float audio -> text through ElevenLabs Scribe. Raises if the call fails."""
    URL = "https://api.elevenlabs.io/v1/speech-to-text"

    def __init__(self, api_key, model="scribe_v2", keyterms=ER_TERMS, timeout=8):
        self.api_key, self.model, self.keyterms, self.timeout = api_key, model, list(keyterms), timeout

    def __call__(self, audio):
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()  # raw 16-bit mono: no encoding step either side
        fields = [("model_id", self.model), ("file_format", "pcm_s16le_16"), ("language_code", "en"),
                  ("tag_audio_events", "false")] + [("keyterms", t) for t in self.keyterms]
        boundary = uuid.uuid4().hex
        body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields)
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.pcm"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n').encode() + pcm + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(self.URL, data=body, headers={
            "xi-api-key": self.api_key, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return (json.loads(response.read()).get("text") or "").strip()


class SpeechPipeline:
    """VAD -> segmenter -> transcriber. feed() takes 512-sample float32 blocks at 16 kHz and
    calls on_event(kind, utt_id, text) with kind "interim" or "final".
    final_transcriber, if given, writes the final text of each utterance; `transcriber` still writes the
    interim text, and the final one too whenever final_transcriber raises."""

    def __init__(self, transcriber, on_event, segmenter=None, final_transcriber=None):
        from silero_vad import load_silero_vad

        self.vad = load_silero_vad()
        self.transcriber, self.on_event = transcriber, on_event
        self.final_transcriber = final_transcriber
        self.seg = segmenter or UtteranceSegmenter()
        self.utt_id = 0
        self.in_speech = False
        self.epoch = self.fed_epoch = 0

    def reset(self):
        """Forget everything heard so far: the utterance in progress is dropped, and so is one being transcribed.
        May be called from another thread; the audio is dropped at the next feed()."""
        self.epoch += 1
        self.in_speech = False

    def feed(self, block, skip_interim=False):
        import torch

        epoch = self.epoch
        if epoch != self.fed_epoch:  # reset() since the last block: start again from silence
            self.fed_epoch = epoch
            self.seg.reset()
            self.vad.reset_states()
        prob = self.vad(torch.from_numpy(block), 16000).item()
        for kind, audio in self.seg.push(block, prob):
            if kind == "interim" and skip_interim:
                continue
            t0 = time.perf_counter()
            text = None
            if kind == "final" and self.final_transcriber is not None:
                try:
                    text = self.final_transcriber(audio)
                except Exception as e:
                    log.warning("cloud speech-to-text failed, using the local model for this one: %s", e)
            if text is None:
                text = self.transcriber(audio)
            if self.epoch != epoch:  # reset() while this was being transcribed: it is audio from before
                return
            if text:
                self.on_event(kind, self.utt_id, text)
            if kind == "final":
                metrics.log("asr.final", compute_ms=round((time.perf_counter() - t0) * 1000), audio_s=round(len(audio) / 16000, 2),
                            empty=not text)
                self.utt_id += 1
        self.in_speech = self.seg.buf is not None


class UtteranceSegmenter:
    """Turns a stream of (audio block, speech probability) into "interim" and "final" events,
    each carrying the utterance audio so far."""

    def __init__(self, sr=16000, block=512, start_thr=0.5, end_silence_ms=600, preroll_ms=200,
                 max_ms=20000, interim_ms=700, min_speech_ms=250):
        self.block_ms = block / sr * 1000
        self.start_thr, self.end_silence_ms, self.max_ms = start_thr, end_silence_ms, max_ms
        self.interim_ms, self.min_speech_ms = interim_ms, min_speech_ms
        self.preroll = collections.deque(maxlen=int(preroll_ms // self.block_ms))
        self.buf = None

    def push(self, block, prob):
        if self.buf is None:
            if prob >= self.start_thr:
                self.buf = list(self.preroll) + [block]
                self.speech_ms, self.silence_ms, self.since_interim = self.block_ms, 0.0, 0.0
            else:
                self.preroll.append(block)
            return []

        self.buf.append(block)
        if prob >= self.start_thr:
            self.speech_ms += self.block_ms
            self.silence_ms = 0.0
        else:
            self.silence_ms += self.block_ms
        self.since_interim += self.block_ms

        if self.silence_ms >= self.end_silence_ms:
            return self._end(keep=self.speech_ms >= self.min_speech_ms)
        if len(self.buf) * self.block_ms >= self.max_ms:
            return self._end(keep=True)
        if self.since_interim >= self.interim_ms:
            self.since_interim = 0.0
            return [("interim", np.concatenate(self.buf))]
        return []

    def _end(self, keep):
        audio = np.concatenate(self.buf)
        self.reset()
        return [("final", audio)] if keep else []

    def reset(self):
        """Drop the utterance in progress and the audio kept from just before it."""
        self.buf = None
        self.preroll.clear()


class MicAsr:
    """Microphone capture thread. The sounddevice callback only queues blocks; a worker thread
    runs the pipeline. Interims are skipped while the worker is behind so finals stay fast."""

    def __init__(self, pipeline, device=None, on_level=None, backlog_blocks=10):
        import queue

        self.pipeline, self.device, self.on_level = pipeline, device, on_level
        self.backlog_blocks = backlog_blocks
        self.queue = queue.Queue()
        self.paused = False
        self.muted_until = 0.0
        self.running = False

    def set_paused(self, paused):
        """Pausing stops listening at once and throws away what was being said; resuming starts from silence."""
        import queue

        self.paused = paused
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self.pipeline.reset()

    def mute_for(self, seconds):
        """Ignore the microphone for a while: the app is about to play sound that must not be captioned."""
        self.muted_until = max(self.muted_until, time.monotonic() + seconds)

    def _callback(self, indata, frames, time_info, status):
        if self.paused or time.monotonic() < self.muted_until:
            return
        block = indata[:, 0].copy()
        self.queue.put(block)
        if self.on_level:
            self.on_level(float(np.sqrt(np.mean(block ** 2))))

    def step(self, timeout=0.2):
        import queue

        try:
            block = self.queue.get(timeout=timeout)
        except queue.Empty:
            return
        self.pipeline.feed(block, skip_interim=self.queue.qsize() > self.backlog_blocks)

    def start(self):
        import threading

        import sounddevice as sd

        self.stream = sd.InputStream(samplerate=16000, blocksize=512, channels=1, dtype="float32",
                                     device=self.device, callback=self._callback)
        self.stream.start()
        self.running = True
        threading.Thread(target=self._run, daemon=True, name="asr").start()

    def _run(self):
        while self.running:
            self.step()

    def stop(self):
        self.running = False
        self.stream.stop()
        self.stream.close()
