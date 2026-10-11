import threading

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from medbridge.server import create_app
    return create_app(engines=False, patient_local_only=False)


def test_mic_gate_is_off_unless_switched_on(monkeypatch):
    from medbridge.server import mic_gate_db

    monkeypatch.setenv("MIC_GATE_DB", "-35")
    monkeypatch.delenv("MIC_GATE", raising=False)
    assert mic_gate_db() is None
    monkeypatch.setenv("MIC_GATE", "0")
    assert mic_gate_db() is None
    monkeypatch.setenv("MIC_GATE", "1")
    assert mic_gate_db() == -35.0


def test_ws_sends_snapshot_on_connect(app):
    with TestClient(app) as c, c.websocket_connect("/ws?role=doctor") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state" and msg["state"]["captions"] == []


def test_engine_events_from_threads_reach_both_views(app):
    with TestClient(app) as c, c.websocket_connect("/ws?role=doctor") as doc, c.websocket_connect("/ws?role=patient") as pat:
        doc.receive_json(); pat.receive_json()
        t = threading.Thread(target=app.state.hub.on_caption, args=("final", 0, "Are you in pain?"))
        t.start(); t.join()
        for ws in (doc, pat):
            assert ws.receive_json()["state"]["captions"][0]["text"] == "Are you in pain?"


def test_patient_confirm_reaches_doctor(app):
    with TestClient(app) as c, c.websocket_connect("/ws?role=doctor") as doc, c.websocket_connect("/ws?role=patient") as pat:
        doc.receive_json(); pat.receive_json()
        # Natural signing is disabled in the app for now, so the draft is typed instead of coming from a signed sentence:
        # app.state.hub.on_sentence({"seg_id": 1, "latency_ms": 5,
        #                            "candidates": [{"text": "My stomach hurts.", "score": -0.3, "rel_score": 1.0}]})
        pat.send_json({"type": "draft.edit", "text": "My stomach hurts."})
        doc.receive_json(); pat.receive_json()
        pat.send_json({"type": "draft.confirm"})
        assert doc.receive_json()["state"]["messages"][0]["text"] == "My stomach hurts."


def test_landmarks_go_to_patient_view_only(app):
    with TestClient(app) as c, c.websocket_connect("/ws?role=doctor") as doc, c.websocket_connect("/ws?role=patient") as pat:
        doc.receive_json(); pat.receive_json()
        app.state.hub.stream({"type": "landmarks", "hands": [], "body": []})
        app.state.hub.on_caption("final", 0, "x")
        assert pat.receive_json()["type"] == "landmarks"
        assert doc.receive_json()["type"] == "state"


def test_unknown_role_is_rejected(app):
    with TestClient(app) as c:
        with pytest.raises(Exception):
            with c.websocket_connect("/ws?role=admin") as ws:
                ws.receive_json()


def test_broadcast_after_event_loop_closed_is_ignored():
    import asyncio

    from medbridge.server import Clients

    clients = Clients()
    loop = asyncio.new_event_loop()
    clients.loop = loop
    loop.close()
    clients.broadcast({"type": "state", "state": {}})  # engine thread during shutdown: must not raise


def test_malformed_ws_message_does_not_close_socket(app):
    with TestClient(app) as c, c.websocket_connect("/ws?role=patient") as pat:
        pat.receive_json()
        pat.send_json(["not", "an", "object"])
        pat.send_json({"type": "candidate.pick", "index": "x"})
        pat.send_json({"type": "mode.set", "mode": "precise"})
        modes = [pat.receive_json()["state"]["sign"]["mode"] for _ in range(2)]  # ignored pick may echo a snapshot first
        assert modes[-1] == "precise"


def test_patient_controls_and_camera_are_local_only_by_default():
    from medbridge.server import create_app

    app = create_app(engines=False, patient_local_only=True)
    with TestClient(app) as c:  # TestClient connects from host "testclient", i.e. not loopback
        assert c.get("/video.mjpg").status_code == 403
        with pytest.raises(Exception):
            with c.websocket_connect("/ws?role=patient") as ws:
                ws.receive_json()
        with c.websocket_connect("/ws?role=doctor") as ws:
            assert ws.receive_json()["type"] == "state"


def test_confirmed_patient_message_is_spoken_once_and_the_mic_is_muted_while_it_plays():
    from medbridge.server import create_app

    class FakeVoice:
        calls = []

        def speak(self, text):
            self.calls.append(text)
            return b"x" * 32_000                     # 2.0 s of 128 kbit/s mp3

    app = create_app(engines=False, patient_local_only=False, voice=FakeVoice())
    muted = []
    app.state.mute_mic = muted.append
    with TestClient(app) as c:
        assert c.get("/api/config").json() == {"speech": True}
        hub = app.state.hub
        hub.apply({"type": "draft.edit", "text": "Heart hurt."}, role="patient")
        hub.apply({"type": "draft.confirm"}, role="patient")
        mid = hub.state["messages"][0]["id"]
        r = c.get(f"/api/speech/{mid}")
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) == 32_000
        assert c.get(f"/api/speech/{mid}").status_code == 200        # played again
        assert FakeVoice.calls == ["Heart hurt."]                    # ...without asking the service twice
        assert muted == [pytest.approx(3.0), pytest.approx(3.0)]     # clip length plus a second, each time it plays
        assert c.get("/api/speech/999").status_code == 404


def test_speech_is_off_without_a_voice_and_a_service_failure_is_a_502():
    from medbridge.server import create_app

    off = create_app(engines=False, patient_local_only=False)
    with TestClient(off) as c:
        assert c.get("/api/config").json() == {"speech": False}
        assert c.get("/api/speech/1").status_code == 404

    class BrokenVoice:
        def speak(self, text):
            raise OSError("quota exceeded")

    app = create_app(engines=False, patient_local_only=False, voice=BrokenVoice())
    with TestClient(app) as c:
        app.state.hub.apply({"type": "draft.edit", "text": "Help."}, role="patient")
        app.state.hub.apply({"type": "draft.confirm"}, role="patient")
        assert c.get(f"/api/speech/{app.state.hub.state['messages'][0]['id']}").status_code == 502


def test_long_caption_motion_is_served_in_batches_as_it_is_built():
    import time

    import numpy as np

    from medbridge.server import create_app

    release = threading.Event()

    class StreamBuilder:
        def stream(self, text):
            yield np.zeros((12, 178, 3), np.float32), [{"word": "where", "gloss": "WHERE", "source": "aslc", "start": 0, "end": 12}]
            release.wait(2)
            yield np.ones((8, 178, 3), np.float32), [{"word": "hurt", "gloss": "HURT", "source": "aslc", "start": 12, "end": 20}]

    app = create_app(engines=False, patient_local_only=False, sign_builder=StreamBuilder())
    hub = app.state.hub

    def wait_for(check):
        for _ in range(100):
            if check(hub.state.get("signing") or {}):
                return hub.state["signing"]
            time.sleep(0.02)
        raise AssertionError(hub.state.get("signing"))

    with TestClient(app) as c:
        hub.on_caption("final", 0, "where hurt")
        cid = hub.state["captions"][0]["id"]
        sig = wait_for(lambda s: s.get("status") == "ready")          # the first batch is playable right away
        assert sig["frames"] == 12 and sig["done"] is False and [w["word"] for w in sig["words"]] == ["where"]
        first = c.get(f"/api/signing/{cid}").json()
        assert first["frames"] == 12 and first["start"] == 0 and first["done"] is False
        release.set()
        sig = wait_for(lambda s: s.get("done"))
        assert sig["status"] == "ready" and sig["frames"] == 20 and [w["word"] for w in sig["words"]] == ["where", "hurt"]
        rest = c.get(f"/api/signing/{cid}?start=12").json()            # only the frames the page does not have yet
        assert rest["frames"] == 8 and rest["start"] == 12 and rest["total"] == 20 and rest["done"] is True
        assert rest["build"] == first["build"]
        part = c.get(f"/api/signing/{cid}?start=0&limit=5").json()       # a long motion is handed out in pieces
        assert part["frames"] == 5 and part["total"] == 20


def test_final_caption_is_built_into_signing_motion_and_served():
    import time

    import numpy as np

    from medbridge.server import create_app

    class FakeBuilder:
        def build(self, text):
            motion = np.zeros((12, 178, 3), np.float32)
            return motion, [{"word": w, "gloss": w.upper(), "source": "aslc", "start": 0, "end": 12} for w in text.split()]

    app = create_app(engines=False, patient_local_only=False, sign_builder=FakeBuilder())
    with TestClient(app) as c:
        app.state.hub.on_caption("final", 0, "where hurt")
        cid = app.state.hub.state["captions"][0]["id"]
        for _ in range(50):
            if (app.state.hub.state.get("signing") or {}).get("status") == "ready":
                break
            time.sleep(0.02)
        sig = app.state.hub.state["signing"]
        assert sig["caption_id"] == cid and [w["word"] for w in sig["words"]] == ["where", "hurt"]
        body = c.get(f"/api/signing/{cid}").json()
        assert body["frames"] == 12 and body["points"] == 178 and "data" in body
        assert c.get("/api/signing/999").status_code == 404
