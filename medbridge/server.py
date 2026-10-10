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
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
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


def start_engines(app, hub):
    """Load the models and start the camera + microphone threads (runs in a background thread)."""
    import json as _json

    import sounddevice as sd
    import torch

    from medbridge.asr import MicAsr, SpeechPipeline, Transcriber
    from medbridge.islr import load_gloss_list, load_stgcn
    from medbridge.unisign_runner import NaturalSigner
    from medbridge.vision import NaturalEngine, PreciseEngine, Vision

    hub.on_sign_status("loading")
    glosses = load_gloss_list(ROOT / "data/aslc/ASL_Citizen/splits/train.csv")
    vocab = _json.loads((ROOT / "data/medical_vocab.json").read_text())
    precise = PreciseEngine(hub, load_stgcn(ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt", len(glosses)),
                            glosses, vocab)
    signer = NaturalSigner(ROOT / "data/models/openasl_pose_only_slt.pth",
                           device="mps" if torch.backends.mps.is_available() else "cpu",
                           pose_mode=_env("NATURAL_POSE_MODE", "lightweight"))
    natural = NaturalEngine(hub, signer, rest_line=float(_env("REST_LINE", "0.85")))
    vision = Vision(hub, int(_env("CAMERA_INDEX", "0")), {"natural": natural, "precise": precise},
                    mode=hub.state["sign"]["mode"])
    hub.on_mode, hub.on_sign_done = vision.set_mode, vision.force_end
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
    mic.start()
    hub.on_asr_state("listening")
    log.info("engines ready")


def create_app(engines=True, patient_local_only=None):
    """patient_local_only: the camera stream and patient controls are served only to this Mac
    (the doctor view may come from the LAN). Override with PATIENT_LAN=1."""
    load_dotenv(ROOT / ".env")
    if patient_local_only is None:
        patient_local_only = _env("PATIENT_LAN", "0") != "1"
    clients = Clients()
    llm = _env("GLOSS_TRANSLATOR", "literal").lower() == "llm"
    hub = Hub(broadcast=clients.broadcast, translate=make_translator(),
              precise_threshold=float(_env("PRECISE_THRESHOLD", "0.3")),
              natural_min_score=float(_env("NATURAL_MIN_SCORE", "-0.65")),
              async_translate=llm)
    hub.state["sign"]["mode"] = _env("DEFAULT_MODE", "natural")

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
    uvicorn.run(create_app(), host=_env("HOST", "0.0.0.0"), port=int(_env("PORT", "8000")))
