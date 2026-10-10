"""Doctor speech -> live captions: Silero VAD segments utterances, mlx-whisper transcribes them.
Audio stays in memory and is dropped after transcription."""
import collections

import numpy as np

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


class SpeechPipeline:
    """VAD -> segmenter -> transcriber. feed() takes 512-sample float32 blocks at 16 kHz and
    calls on_event(kind, utt_id, text) with kind "interim" or "final"."""

    def __init__(self, transcriber, on_event, segmenter=None):
        from silero_vad import load_silero_vad

        self.vad = load_silero_vad()
        self.transcriber, self.on_event = transcriber, on_event
        self.seg = segmenter or UtteranceSegmenter()
        self.utt_id = 0
        self.in_speech = False

    def feed(self, block, skip_interim=False):
        import torch

        prob = self.vad(torch.from_numpy(block), 16000).item()
        for kind, audio in self.seg.push(block, prob):
            if kind == "interim" and skip_interim:
                continue
            text = self.transcriber(audio)
            if text:
                self.on_event(kind, self.utt_id, text)
            if kind == "final":
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
        self.buf = None
        self.preroll.clear()
        return [("final", audio)] if keep else []


class MicAsr:
    """Microphone capture thread. The sounddevice callback only queues blocks; a worker thread
    runs the pipeline. Interims are skipped while the worker is behind so finals stay fast."""

    def __init__(self, pipeline, device=None, on_level=None, backlog_blocks=10):
        import queue

        self.pipeline, self.device, self.on_level = pipeline, device, on_level
        self.backlog_blocks = backlog_blocks
        self.queue = queue.Queue()
        self.paused = False
        self.running = False

    def _callback(self, indata, frames, time_info, status):
        if self.paused:
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
