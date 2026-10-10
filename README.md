# MEDBRIDGE

Two-way, real-time communication between a Deaf patient who signs American Sign Language (ASL) and a
speaking clinician in an emergency room. Everything runs live on one MacBook. Nothing is
pre-recorded, and the AI output is never faked.

- **Doctor → patient:** the doctor speaks, and the patient reads large live captions. The doctor can correct any caption.
- **Patient → doctor:** the patient signs. The app translates the signing into English candidates, and the patient
  confirms, corrects or rejects them before anything is shown to the doctor as "patient said".

> **Research prototype.** MEDBRIDGE is not a certified medical interpreter. Do not use it for clinical decisions.
> Use a qualified ASL interpreter for care.

## What it can and cannot do

| | Natural signing (default) | One sign at a time (precise) |
|---|---|---|
| Model | [Uni-Sign](https://github.com/ZechengLi19/Uni-Sign) (ICLR 2025), pose-only, fine-tuned on OpenASL | [ASL Citizen](https://github.com/microsoft/ASL-citizen-code) ST-GCN (Microsoft, NeurIPS 2023) |
| Input | A whole sentence, signed naturally. Rest your hands to finish. | One sign, then lower your hands. |
| Output | Top-3 English sentences | Top-5 signs from a 103-label ER vocabulary (`data/medical_vocab.json`) |
| Quality | Research-grade: often gets the gist, often wrong. Low-confidence results are flagged. | 86% top-1 / 98.5% top-5 on held-out Deaf signers (ER vocabulary) |

It **cannot**:
- translate like a human interpreter;
- understand signs outside the training data (for the precise mode, outside the vocabulary);
- reliably read fingerspelling;
- guarantee any translation.

That is why **every patient message is confirmed by the patient**, and why unconfirmed model output is always
labelled as such on the doctor's screen.

Why these two models: no open model for continuous ASL → English translation performs better (checked October 2026).
- Google's SignGemma has not been released.
- Google's SL2T runs only on Pixel 11 and has no API.
- General video LLMs score about 1 BLEU on ASL: Gemini-2.5-Pro 1.4, GPT-5 0.1 on How2Sign.
- SHuBERT has released no translation checkpoint.

Uni-Sign is the strongest open continuous model. ASL Citizen is the strongest open isolated-sign model and is
trained on webcam video from 52 Deaf or hard-of-hearing signers.

## Measured results

All numbers come from running **our** live pipeline code on held-out data (`scripts/eval_*.py`).

| Component | Test | Result | Published |
|---|---|---|---|
| Natural signing (Uni-Sign) | 60 held-out OpenASL test clips, lightweight pose | BLEU-4 **15.5**, chrF 37.7 | BLEU-4 22.7 (full 976-clip test set) |
| | Quality vs. model confidence | Above-median score: chrF 42.6. Below: chrF 21.2 (r = 0.64) | — |
| | Translation latency (M4 Max, MPS) | p50 **498 ms**, max 1.5 s after the sentence ends | — |
| Live camera pipeline | MacBook camera, M4 Max | **30 fps** in both modes (camera limit) | — |
| Precise (ASL Citizen) | 150 random held-out clips, all 2,731 signs | top-1 **60.7%**, top-5 88.0% | 59.5% / 82.7% |
| | 339 held-out clips of ER signs, ER vocabulary | top-1 **86.1%**, top-5 **98.5%** | — |
| Doctor ASR (whisper-large-v3-turbo) | 20 ER sentences × 4 synthetic voices | WER **1.5%**, medical-term recall 100% | — |
| | Caption latency | p50 358 ms compute + 600 ms end-of-speech wait | — |

Notes:
- A larger pose model (rtmlib `performance`) scored lower (BLEU-4 11.4) and runs at about 6 fps, so `lightweight` is used.
- The ASR numbers use synthesized speech. Run `python scripts/eval_asr.py --live` with a real speaker to measure the real case.
- The live signing accuracy depends on the signer. Measure it with the protocol in [Testing](#testing-and-measurement).

## Architecture

```
                         Mac A (patient laptop, runs everything)
 Logitech cam ─► vision.py camera thread (unmirrored frames, memory only)
   ├─ natural ─► rtmlib whole-body pose ─► sentence segmenter ─► Uni-Sign (mT5) on MPS ─► top-3 sentences
   ├─ precise ─► MediaPipe Holistic ─► sign segmenter ─► ST-GCN ─► top-5 signs ─► translate.py
   └─► landmarks (WebSocket, patient view only) + MJPEG preview
 Mic ─► asr.py: Silero VAD ─► utterance segmenter ─► mlx-whisper ─► interim / final captions
 hub.py: session state, role-checked actions ─► WebSocket snapshots ─► /patient and /doctor
```

- Device capture happens in Python, so the doctor's laptop needs no camera or mic permission. It only opens a web page.
- Only the active mode's pose model runs.
- If `GLOSS_TRANSLATOR=llm`, Claude rephrases precise-mode sign labels. Natural-signing output is never rewritten by an LLM.

## Setup (macOS, Apple Silicon)

Requirements: Python 3.11, Node 20+, Homebrew `ffmpeg` (only for `fetch_eval_clips.py`).

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_models.py           # ~3 GB: Uni-Sign, ASL Citizen weights + gloss list, whisper
(cd web && npm install && npm run build)
cp .env.example .env                      # then set CAMERA_INDEX / MIC_NAME
python scripts/check_devices.py           # finds the Logitech camera + mic, checks permissions
```

## Run

```bash
python -m medbridge.server
```

| Who | Where |
|---|---|
| Patient (Mac A, full screen) | http://localhost:8000/patient |
| Doctor (second window on Mac A) | http://localhost:8000/doctor |
| Doctor (second Mac, same Wi-Fi) | `http://<mac-a-name>.local:8000/doctor` |

- Models load in about 20 s. The UI shows "Loading…" until they are ready.
- The camera stream and the patient controls are served only to Mac A itself. Other machines on the network
  can open only the doctor view. Set `PATIENT_LAN=1` to allow the patient view from another machine.
- Frontend development with hot reload: run `cd web && npm run dev`, then open http://localhost:5173/patient.
  The dev server proxies `/ws`, `/video.mjpg` and `/api` to port 8000.

## Live demo procedure

1. **Setup.** Put the Logitech camera at chest height, with even lighting from the front and a plain background.
   The patient sits about 1 m away, waist up in frame, hands resting in the lap.
2. **Doctor:** "Hi, I'm Doctor Lee. What brought you in today?" Captions appear live on the patient screen.
3. **Patient (natural signing):** signs a short sentence, then rests their hands.
   - Three English candidates appear. The patient taps the right one and presses **Confirm & send**.
   - The doctor sees it with "✓ Confirmed by patient".
4. **Doctor:** "On a scale of one to ten, how bad is the pain?"
   - The patient switches to **One sign at a time**, signs a number, and confirms.
   - FIVE and TEN are not in the vocabulary. Use 1–4 or 6–9.
5. **Doctor:** "Are you allergic to penicillin?"
   - If a drug name is mis-transcribed, the doctor clicks the caption and fixes it.
   - The patient sees "Corrected by doctor" with the changed word highlighted.
6. **Honesty moment.** Sign something unusual.
   - Show the "Low confidence" flag or the "Not sure — pick" chip, then the **Retry** and **Signs I can recognize** panels.
7. **Finish.** Show the doctor's System panel (fps and latency), then the results table above.

Tips:
- Rehearse the precise-mode signs with the ASL-LEX / Signing Savvy videos for the exact citation forms.
- Pause briefly before and after signing.

## Testing and measurement

Step-by-step test examples for one Mac (signs, sentences, doctor lines, what to record) are in
[docs/testing.md](docs/testing.md).

```bash
pytest                                   # 69 tests: parity with upstream preprocessing, segmenters, hub, server, ASR
(cd web && npx vitest run)               # frontend helpers
python scripts/fetch_eval_clips.py --n 60 && python scripts/eval_unisign.py --pose-mode lightweight
python scripts/eval_islr.py --n-random 150 --per-gloss 3
python scripts/eval_asr.py               # add --live for a real speaker
METRICS_LOG=1 python -m medbridge.server # logs timings/scores/labels (no text/audio/video) to data/metrics.jsonl
```

**Live signing protocol (Phase 6):**
- **Precise mode:** sign each ER sign 5 times and note top-1 and top-5 per sign.
- **Natural mode:** sign the 20 patient sentences in `data/er_phrases.json`. Judge whether the meaning is right in the top-1 and in the top-3.
- **False recognition:** spend 2 minutes not signing (talking, scratching your face, adjusting glasses). Count the outputs that are *not* flagged.
- **Successful exchanges:** run 10 scripted question-and-answer exchanges. Count those confirmed with the correct meaning and without typing.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Camera unavailable" / black frames | System Settings → Privacy & Security → Camera: enable the app running Python (Terminal, iTerm or VS Code), then restart that app. Check `CAMERA_INDEX` with `scripts/check_devices.py`. Continuity Camera (an iPhone) can take index 0. |
| No captions; mic level flat | Privacy & Security → Microphone, same as above. Set `MIC_NAME=Logitech` to use the webcam mic. |
| `module 'mediapipe' has no attribute 'solutions'` | Install exactly `mediapipe==0.10.21`. Later versions removed `solutions`. |
| CoreML error from onnxruntime (YOLOX shape) | The person detector must stay on CPU. Only the pose model runs on CoreML (`make_pose` in `unisign_runner.py`). |
| Low camera fps in natural mode | The System panel on the doctor view shows fps; expect about 30. Use `NATURAL_POSE_MODE=lightweight` and keep the laptop plugged in. |
| Doctor's Mac can't connect | Use the same Wi-Fi, keep `HOST=0.0.0.0`, and allow incoming connections for Python in the macOS firewall prompt. |
| `GLOSS_TRANSLATOR=llm` shows "literal" | No or invalid Claude credentials (`ANTHROPIC_API_KEY` or `ant auth login`), or the network is down. The app falls back to literal text by design. |
| MPS errors | `PYTORCH_ENABLE_MPS_FALLBACK=1 python -m medbridge.server` |

## Privacy and safety

- Audio and video are processed in memory and never written to disk. No recordings are made.
- Speech recognition runs locally.
- The only network call is the optional Claude rephrasing of precise-mode sign labels.
- The conversation lives in memory until **End session**.
- There is no diagnosis or clinical decision support.

## Project layout

```
medbridge/   server.py hub.py vision.py segmenter.py asr.py translate.py metrics.py
             unisign/ (trimmed Uni-Sign pose model)  unisign_runner.py
             islr.py  stgcn/ (vendored ASL Citizen ST-GCN, MIT)
web/         React + Vite + Tailwind + Motion: patient (dark) and clinician (light) views
scripts/     check_devices, fetch_models, fetch_eval_clips, eval_unisign, eval_islr, eval_asr
data/        medical_vocab.json, er_phrases.json (everything else here is downloaded and gitignored)
tests/       pytest suite
```

## Attribution and licenses

- **Uni-Sign:** Li et al., *Uni-Sign: Toward Unified Sign Language Understanding at Scale*, ICLR 2025.
  The model and preprocessing code in `medbridge/unisign/` are adapted from https://github.com/ZechengLi19/Uni-Sign.
  The upstream repository has no license file, so treat this use as research and evaluation only.
- **ASL Citizen:** Desai et al., NeurIPS 2023 Datasets & Benchmarks.
  The code and weights are MIT (`medbridge/stgcn/LICENSE`).
  The dataset (only its split CSVs and a few test videos are fetched) is under the Microsoft Research License Terms in `use.txt`.
- **OpenASL:** Shi et al., 2022. Test clips are fetched from YouTube only for offline evaluation and are not redistributed.
- **Whisper:** OpenAI, run through `mlx-whisper`.
- **Silero VAD:** MIT.
- **rtmlib / RTMPose:** Apache-2.0.
- **MediaPipe:** Apache-2.0.
