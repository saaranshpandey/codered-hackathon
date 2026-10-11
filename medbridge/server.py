"""MEDBRIDGE backend: FastAPI app wiring the hub, the camera/sign engines and the doctor ASR.

Run: python -m medbridge.server   (settings come from .env, see .env.example)"""
import asyncio
import contextlib
import json
import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from medbridge.hub import Hub
from medbridge.translate import make_translator

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web/dist"
PATIENT_ONLY = {"landmarks"}
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
DROPPABLE = {"landmarks", "level"}
log = logging.getLogger("medbridge")


class Clients:
    """WebSocket fan-out. broadcast() is thread-safe; each connection has its own ordered queue."""

    def __init__(self):
        self.queues = {}
        self.loop = None

    def broadcast(self, msg):
        if self.loop is None or self.loop.is_closed():
            return  # not started yet, or shutting down while engine threads still run
        try:
            self.loop.call_soon_threadsafe(self._enqueue, msg["type"], json.dumps(msg))
        except RuntimeError:  # loop closed between the check and the call
            pass

    def _enqueue(self, kind, data):
        for queue, role in list(self.queues.values()):
            if kind in PATIENT_ONLY and role != "patient":
                continue
            if kind in DROPPABLE and queue.qsize() > 20:
                continue  # slow client: skip high-rate frames, never state
            queue.put_nowait(data)


def _env(name, default):
    return os.environ.get(name, default)


class SignWorker:
    """Builds the signing motion for the doctor's newest caption in the background and hands it out in batches,
    so signing can start before a long caption is finished. Only the newest caption is built: when another one
    arrives, the rest of the current one is dropped. Motion is kept in memory (never on disk)."""

    def __init__(self, hub, builder, keep=20):
        self.hub, self.builder, self.keep = hub, builder, keep
        self.motions = {}  # caption_id -> {"build", "chunks", "frames", "words", "done"}
        self.builds = 0    # counts builds, so a client can tell a rebuilt caption (a correction) from more batches
        self.pending = None
        self.cv = threading.Condition()
        if hasattr(builder, "warm"):
            builder.warm()
        threading.Thread(target=self._run, daemon=True, name="signing").start()

    def submit(self, caption_id, text):
        with self.cv:
            self.pending = (caption_id, text)
            self.cv.notify()

    def prefetch(self, text):
        """An interim caption: start fetching its signs now, so they are ready when the final caption arrives."""
        if hasattr(self.builder, "prefetch"):
            self.builder.prefetch(text)

    def chunk(self, caption_id, start=0, limit=720):
        """The motion from frame `start` on, as far as it has been built, at most `limit` frames (24 s) at a time:
        the page asks again for the rest, so even a long caption starts playing after one small response."""
        import numpy as np

        from medbridge.text2sign import N_POINTS, payload

        with self.cv:
            m = self.motions.get(caption_id)
            if m is None:
                return None
            chunks, words, meta = list(m["chunks"]), list(m["words"]), {"build": m["build"], "total": m["frames"], "done": m["done"]}
        motion = np.concatenate(chunks)[start:start + limit] if chunks else np.zeros((0, N_POINTS, 3), np.float32)
        return {**payload(caption_id, motion, words), "start": start, **meta}

    def _publish(self, caption_id, m, status):
        self.hub.on_signing({"caption_id": caption_id, "status": status, "words": list(m["words"]) or None,
                             "frames": m["frames"], "fps": 30, "build": m["build"], "done": m["done"]})

    def _run(self):
        while True:
            with self.cv:
                self.cv.wait_for(lambda: self.pending is not None)
                caption_id, text = self.pending
                self.pending = None
                self.builds += 1
                m = self.motions[caption_id] = {"build": self.builds, "chunks": [], "frames": 0, "words": [], "done": False}
                for old in sorted(self.motions)[:-self.keep]:
                    del self.motions[old]
            self._publish(caption_id, m, "building")
            failed = False
            try:
                # A builder without stream() (a test double) gives the whole motion as one batch.
                batches = self.builder.stream(text) if hasattr(self.builder, "stream") else [self.builder.build(text)]
                for motion, timeline in batches:
                    with self.cv:
                        m["chunks"].append(motion)
                        m["frames"] += int(len(motion))
                        m["words"] += timeline
                        newer = self.pending is not None
                    if newer:  # the doctor has said something else: the rest of this caption is not built
                        break
                    if m["frames"]:
                        self._publish(caption_id, m, "ready")
            except Exception:
                log.exception("signing build failed")
                failed = True
            with self.cv:
                m["done"] = True
            self._publish(caption_id, m, "error" if failed and not m["frames"] else "ready" if m["frames"] else "empty")


def make_sign_builder():
    import csv as _csv

    from medbridge.text2sign import AslCitizenSigns, Builder, SignMT, build_lexicon

    with open(ROOT / "data/aslc/ASL_Citizen/splits/train.csv") as f:
        glosses = {r[2].strip() for r in list(_csv.reader(f))[1:]}
    signmt = SignMT(ROOT) if _env("SIGN_MT", "1") == "1" else None
    return Builder(build_lexicon(glosses), AslCitizenSigns(ROOT), signmt)


def start_engines(app, hub):
    """Load the models and start the camera + microphone threads (runs in a background thread)."""
    import json as _json

    import sounddevice as sd
    # import torch  # only chose the device for the natural-signing model

    from medbridge.asr import MicAsr, SpeechPipeline, Transcriber
    from medbridge.islr import load_gloss_list, load_stgcn
    # Natural signing (Uni-Sign) is disabled for now. To re-enable, restore the commented lines in this function and in
    # create_app below, and the natural-signing parts of web/src/components/PatientView.tsx.
    # from medbridge.unisign_runner import NaturalSigner
    # from medbridge.vision import NaturalEngine
    from medbridge.vision import PreciseEngine, Vision

    hub.on_sign_status("loading")
    glosses = load_gloss_list(ROOT / "data/aslc/ASL_Citizen/splits/train.csv")
    vocab = _json.loads((ROOT / "data/medical_vocab.json").read_text())
    precise = PreciseEngine(hub, load_stgcn(ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt", len(glosses)),
                            glosses, vocab)
    # signer = NaturalSigner(ROOT / "data/models/openasl_pose_only_slt.pth",
    #                        device="mps" if torch.backends.mps.is_available() else "cpu",
    #                        pose_mode=_env("NATURAL_POSE_MODE", "lightweight"),
    #                        phrases=_json.loads((ROOT / "data/er_phrases.json").read_text())["patient"])
    # natural = NaturalEngine(hub, signer, rest_line=float(_env("REST_LINE", "0.85")))
    # vision = Vision(hub, int(_env("CAMERA_INDEX", "0")), {"natural": natural, "precise": precise},
    #                 mode=hub.state["sign"]["mode"])
    vision = Vision(hub, int(_env("CAMERA_INDEX", "0")), {"precise": precise}, mode=hub.state["sign"]["mode"])
    hub.on_mode, hub.on_sign_done, hub.on_sign_start = vision.set_mode, vision.force_end, vision.start_signing
    hub.on_sign_enable = vision.set_enabled
    vision.enabled = hub.state["sign"]["enabled"]  # the switch may have been used while the models were loading
    app.state.vision = vision
    vision.start()

    hub.on_asr_state("loading")
    mic_name, device = _env("MIC_NAME", ""), None
    if mic_name:
        device = next((i for i, d in enumerate(sd.query_devices())
                       if d["max_input_channels"] > 0 and mic_name.lower() in d["name"].lower()), None)
    pipeline = SpeechPipeline(Transcriber(), hub.on_caption)
    last = [0.0]

    def on_level(rms):
        now = time.monotonic()
        if now - last[0] > 0.066:
            last[0] = now
            hub.stream({"type": "level", "level": round(rms, 4)})
            hub.on_asr_state("speech" if pipeline.in_speech else "listening")

    mic = MicAsr(pipeline, device=device, on_level=on_level)
    hub.on_asr_pause = lambda paused: setattr(mic, "paused", paused)
    app.state.mute_mic = mic.mute_for
    mic.start()
    hub.on_asr_state("listening")
    log.info("engines ready")


def create_app(engines=True, patient_local_only=None, sign_builder=None, voice=None):
    """patient_local_only: the camera stream and patient controls are served only to this Mac
    (the doctor view may come from the LAN). Override with PATIENT_LAN=1.
    voice: speaks confirmed patient messages on the doctor view; by default ElevenLabs, if a key is set."""
    load_dotenv(ROOT / ".env")
    if patient_local_only is None:
        patient_local_only = _env("PATIENT_LAN", "0") != "1"
    clients = Clients()
    llm = _env("GLOSS_TRANSLATOR", "literal").lower() == "llm"
    hub = Hub(broadcast=clients.broadcast, translate=make_translator(),
              precise_threshold=float(_env("PRECISE_THRESHOLD", "0.3")),
              natural_min_score=float(_env("NATURAL_MIN_SCORE", "-0.65")),
              phrase_min_score=float(_env("PHRASE_MIN_SCORE", "-1.5")),
              async_translate=llm,
              modes=("precise",))  # natural signing is disabled for now; drop this argument to offer both modes
    # hub.state["sign"]["mode"] = _env("DEFAULT_MODE", "natural")
    hub.state["sign"]["mode"] = "precise"
    if sign_builder is None and engines and _env("SIGNING", "1") == "1":
        sign_builder = make_sign_builder()
    signer = SignWorker(hub, sign_builder) if sign_builder is not None else None
    if voice is None and engines:
        from medbridge.speech import make_voice
        voice = make_voice()
    speaker = None
    if voice is not None:
        from medbridge.speech import Speaker
        speaker = Speaker(hub, voice)
    if signer:
        hub.on_final_caption = signer.submit
        hub.on_interim_caption = signer.prefetch

    @contextlib.asynccontextmanager
    async def lifespan(app):
        clients.loop = asyncio.get_running_loop()
        if engines:
            threading.Thread(target=start_engines, args=(app, hub), daemon=True, name="startup").start()
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.hub, app.state.clients, app.state.vision = hub, clients, None

    @app.get("/")
    def root():
        return RedirectResponse("/patient")

    @app.get("/patient")
    @app.get("/doctor")
    def spa():
        index = DIST / "index.html"
        if not index.exists():
            return PlainTextResponse("Frontend not built: run `npm run build` in web/", status_code=503)
        return FileResponse(index)

    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/api/vocab")
    def vocab():
        labels = json.loads((ROOT / "data/medical_vocab.json").read_text()).values()
        return JSONResponse(list(dict.fromkeys(labels)))

    @app.get("/api/config")
    def config():
        return JSONResponse({"speech": speaker is not None})

    @app.get("/api/speech/{message_id}")
    def speech(message_id: int):
        """A confirmed patient message as mp3, for the doctor view to play."""
        from medbridge.speech import seconds

        if speaker is None:
            return PlainTextResponse("speech is off", status_code=404)
        try:
            audio = speaker.get(message_id)
        except Exception as e:
            log.warning("speech failed for message %s: %s", message_id, e)
            return PlainTextResponse("speech service failed", status_code=502)
        if audio is None:
            return PlainTextResponse("not found", status_code=404)
        mute = getattr(app.state, "mute_mic", None)
        if mute:  # the doctor's microphone would hear this and caption it as the doctor's words
            mute(seconds(audio) + 1.0)
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/signing/{caption_id}")
    def signing(caption_id: int, start: int = 0, limit: int = 720):
        body = signer.chunk(caption_id, max(0, start), max(1, limit)) if signer else None
        return JSONResponse(body) if body else PlainTextResponse("not found", status_code=404)

    @app.get("/video.mjpg")
    def video(request: Request):
        if patient_local_only and request.client.host not in LOOPBACK:
            return PlainTextResponse("camera stream is only served to the patient's machine", status_code=403)
        if app.state.vision is None:
            return PlainTextResponse("camera not started", status_code=503)
        return StreamingResponse(app.state.vision.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket, role: str = ""):
        if role not in ("patient", "doctor") or (
                role == "patient" and patient_local_only and ws.client.host not in LOOPBACK):
            await ws.close(code=1008)
            return
        await ws.accept()
        queue = asyncio.Queue()
        clients.queues[id(ws)] = (queue, role)
        queue.put_nowait(json.dumps(hub.snapshot()))

        async def writer():
            while True:
                await ws.send_text(await queue.get())

        task = asyncio.create_task(writer())
        try:
            while True:
                try:
                    msg = json.loads(await ws.receive_text())
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    hub.apply(msg, role)
        except WebSocketDisconnect:
            pass
        finally:
            clients.queues.pop(id(ws), None)
            task.cancel()

    return app


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    load_dotenv(ROOT / ".env")
    # The MJPEG camera stream never ends on its own, so cap graceful shutdown or Ctrl+C waits forever.
    uvicorn.run(create_app(), host=_env("HOST", "0.0.0.0"), port=int(_env("PORT", "8000")), timeout_graceful_shutdown=2)
