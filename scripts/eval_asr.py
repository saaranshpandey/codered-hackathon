"""Doctor ASR accuracy and latency on the scripted ER sentences in data/er_phrases.json.

  --tts   (default) synthesized speech in several macOS voices, streamed through the real
          pipeline (Silero VAD -> segmenter -> mlx-whisper). Repeatable baseline.
  --live  a person reads each sentence into the microphone.
  --engine elevenlabs   final text from ElevenLabs Scribe (as with ASR_ENGINE=elevenlabs; needs ELEVENLABS_API_KEY
          in .env and sends the audio to ElevenLabs). Default: whisper, on this Mac.

Latency reported = compute time from the end-of-speech decision to the final caption; the
end-of-speech decision itself waits 600 ms of silence, so add that for speaker-perceived delay.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import jiwer
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.asr import ElevenLabsTranscriber, SpeechPipeline, Transcriber  # noqa: E402

VOICES = ["Samantha", "Daniel", "Karen", "Aman"]
TERMS = ["chest pain", "penicillin", "aspirin", "blood thinners", "nausea", "vomiting", "unconscious", "consciousness",
         "pregnant", "ct scan", "ibuprofen", "dizzy", "fever", "chills", "iv", "blood pressure", "diabetes", "short of breath"]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", s.lower().replace("dr.", "doctor"))).strip()


def tts(text, voice):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run(["say", "-v", voice, "-o", f.name, "--file-format=WAVE", "--data-format=LEI16@16000", text], check=True)
        with wave.open(f.name) as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def stream(pipe, audio, finals, lat):
    padded = np.concatenate([np.zeros(8000, np.float32), audio, np.zeros(16000, np.float32)])
    for i in range(0, len(padded) - 511, 512):
        n = len(finals)
        t0 = time.perf_counter()
        pipe.feed(padded[i:i + 512])
        if len(finals) > n:
            lat.append((time.perf_counter() - t0) * 1000)


def live_utterance(pipe, finals, lat, timeout=15):
    import sounddevice as sd

    n = len(finals)
    with sd.InputStream(samplerate=16000, blocksize=512, channels=1, dtype="float32") as s:
        end = time.time() + timeout
        while len(finals) == n and time.time() < end:
            block, _ = s.read(512)
            t0 = time.perf_counter()
            pipe.feed(block[:, 0].copy(), skip_interim=True)
            if len(finals) > n:
                lat.append((time.perf_counter() - t0) * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--engine", choices=["whisper", "elevenlabs"], default="whisper")
    args = ap.parse_args()

    sentences = json.loads((ROOT / "data/er_phrases.json").read_text())["doctor"]
    finals, lat = [], []
    cloud = None
    if args.engine == "elevenlabs":
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        cloud = ElevenLabsTranscriber(os.environ["ELEVENLABS_API_KEY"].strip())
    pipe = SpeechPipeline(Transcriber(), lambda kind, utt, text: kind == "final" and finals.append(text),
                          final_transcriber=cloud)
    refs, hyps = [], []
    runs = [(s, None) for s in sentences] if args.live else [(s, v) for v in VOICES for s in sentences]
    for sentence, voice in runs:
        n = len(finals)
        if args.live:
            input(f"\nRead aloud, then pause:  “{sentence}”   [Enter to start]")
            live_utterance(pipe, finals, lat)
        else:
            stream(pipe, tts(sentence, voice), finals, lat)
        hyp = " ".join(finals[n:])
        refs.append(norm(sentence)); hyps.append(norm(hyp))
        print(f"[{voice or 'live'}] {sentence}\n        -> {hyp}")

    wer = jiwer.wer(refs, hyps)
    present = [(t, r, h) for r, h in zip(refs, hyps) for t in TERMS if f" {t} " in f" {r} "]
    recall = sum(f" {t} " in f" {h} " for t, _, h in present) / max(1, len(present))
    print(f"\n== {args.engine}: {len(refs)} utterances  WER {wer * 100:.1f}%  medical-term recall {recall * 100:.0f}% ({len(present)} terms)")
    if lat:
        print(f"   final-caption compute latency ms: p50 {statistics.median(lat):.0f}  p95 {np.percentile(lat, 95):.0f}"
              f"  (+600 ms end-of-speech wait)")


if __name__ == "__main__":
    main()
