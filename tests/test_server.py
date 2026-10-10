import threading

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from medbridge.server import create_app
    return create_app(engines=False, patient_local_only=False)


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
        app.state.hub.on_sentence({"seg_id": 1, "latency_ms": 5,
                                   "candidates": [{"text": "My stomach hurts.", "score": -0.3, "rel_score": 1.0}]})
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
