"""Session state shared by the patient and doctor views.

Engines (ASR, vision) call on_* from their threads; WebSocket clients call apply().
Every state change is broadcast as a full {"type": "state"} snapshot. High-rate streams
(landmarks, mic level) bypass the state and go out through stream()."""
import copy
import threading
import time

from medbridge import metrics
from medbridge.translate import literal

PATIENT_ACTIONS = {"mode.set", "candidate.pick", "sign.pick", "sign.remove", "draft.edit",
                   "draft.confirm", "draft.clear", "sign.start", "sign.done"}
DOCTOR_ACTIONS = {"caption.correct", "asr.pause", "asr.resume", "session.end"}


def _fresh(mode="natural", asr_state="listening"):
    return {
        "captions": [], "interim": None, "messages": [],
        "asr": {"state": asr_state},
        "sign": {"mode": mode, "state": "idle"},
        "natural": None, "precise": [],
        "draft": {"text": "", "source": "", "edited": False},
        "signing": None,  # doctor's latest caption as signing motion: {caption_id, status, words, frames, fps}
    }


def _natural_source(candidate):
    return "natural-phrase" if candidate.get("kind") == "phrase" else "natural"


class Hub:
    def __init__(self, broadcast, translate, on_mode=None, on_asr_pause=None, on_sign_done=None, on_sign_start=None,
                 on_final_caption=None,
                 precise_threshold=0.3, natural_min_score=-1.0, phrase_min_score=-1.5, async_translate=False):
        self.broadcast, self.translate = broadcast, translate
        self.on_mode, self.on_asr_pause, self.on_sign_done = on_mode, on_asr_pause, on_sign_done
        self.on_sign_start = on_sign_start
        self.on_final_caption = on_final_caption
        self.precise_threshold, self.natural_min_score = precise_threshold, natural_min_score
        self.phrase_min_score = phrase_min_score
        self.async_translate = async_translate
        self.lock = threading.RLock()
        self.state = _fresh()
        self._next_id = 0
        self._precise_version = 0

    # ---- helpers -------------------------------------------------------------------------
    def _id(self):
        self._next_id += 1
        return self._next_id

    def _publish(self):
        self.broadcast({"type": "state", "state": copy.deepcopy(self.state)})

    def snapshot(self):
        with self.lock:
            return {"type": "state", "state": copy.deepcopy(self.state)}

    def stream(self, msg):
        self.broadcast(msg)

    def _clear_draft(self):
        self.state["natural"] = None
        self.state["precise"] = []
        self.state["draft"] = {"text": "", "source": "", "edited": False}

    def _rebuild_precise_draft(self):
        labels = [i["chosen"] for i in self.state["precise"] if i["chosen"]]
        self._precise_version += 1
        if not labels:
            self.state["draft"] = {"text": "", "source": "", "edited": False}
            return
        if not self.async_translate:
            text, source = self.translate(labels)
            self.state["draft"] = {"text": text, "source": source, "edited": False}
            return
        # Show the literal text at once; replace it when the (slower) translator returns.
        text, source = literal(labels)
        self.state["draft"] = {"text": text, "source": source, "edited": False}
        version = self._precise_version

        def work():
            text, source = self.translate(labels)
            with self.lock:
                if version == self._precise_version and not self.state["draft"]["edited"]:
                    self.state["draft"] = {"text": text, "source": source, "edited": False}
                    self._publish()

        threading.Thread(target=work, daemon=True).start()

    # ---- engine events -------------------------------------------------------------------
    def on_caption(self, kind, utt_id, text):
        with self.lock:
            if kind == "interim":
                self.state["interim"] = {"id": utt_id, "text": text}
            else:
                self.state["interim"] = None
                cid = self._id()
                self.state["captions"].append({"id": cid, "text": text, "original": None, "t": time.time()})
                if self.on_final_caption:
                    self.on_final_caption(cid, text)
            self._publish()

    def on_signing(self, info):
        with self.lock:
            self.state["signing"] = info
            self._publish()

    def on_asr_state(self, state):
        with self.lock:
            if self.state["asr"]["state"] != "paused" and self.state["asr"]["state"] != state:
                self.state["asr"]["state"] = state
                self._publish()

    def on_sign_status(self, state):
        with self.lock:
            if self.state["sign"]["state"] != state:
                self.state["sign"]["state"] = state
                self._publish()

    def on_sentence(self, result):
        with self.lock:
            if self.state["sign"]["mode"] == "precise":
                return  # translation finished after the patient switched modes
            phrases, free = result.get("phrases") or [], result["candidates"]
            # Closest ER-bank phrases first, then the model's own free translation as a fallback.
            cands = [{**p, "kind": "phrase"} for p in phrases] + [{**c, "kind": "free"} for c in (free[:1] if phrases else free)]
            low = phrases[0]["score"] < self.phrase_min_score if phrases else free[0]["score"] < self.natural_min_score
            self.state["natural"] = {"seg_id": result["seg_id"], "candidates": cands, "latency_ms": result.get("latency_ms"),
                                     "selected": 0, "low_confidence": low}
            self.state["draft"] = {"text": cands[0]["text"], "source": _natural_source(cands[0]), "edited": False}
            self._publish()

    def on_sign_prediction(self, seg_id, topk, latency_ms=None):
        with self.lock:
            if self.state["sign"]["mode"] == "natural":
                return
            uncertain = not topk or topk[0]["p"] < self.precise_threshold
            self.state["precise"].append({"seg_id": seg_id, "topk": topk, "uncertain": uncertain,
                                          "chosen": None if uncertain else topk[0]["label"],
                                          "latency_ms": latency_ms})
            self._rebuild_precise_draft()
            self._publish()

    # ---- client actions ------------------------------------------------------------------
    def apply(self, msg, role):
        kind = msg.get("type")
        allowed = PATIENT_ACTIONS if role == "patient" else DOCTOR_ACTIONS if role == "doctor" else set()
        if kind not in allowed:
            return
        with self.lock:
            s = self.state
            if kind == "mode.set" and msg.get("mode") in ("natural", "precise"):
                s["sign"]["mode"] = msg["mode"]
                self._clear_draft()
                if self.on_mode:
                    self.on_mode(msg["mode"])
            elif kind == "candidate.pick" and s["natural"]:
                i = msg.get("index")
                if isinstance(i, int) and 0 <= i < len(s["natural"]["candidates"]):
                    s["natural"]["selected"] = i
                    cand = s["natural"]["candidates"][i]
                    s["draft"] = {"text": cand["text"], "source": _natural_source(cand), "edited": False}
            elif kind == "sign.pick":
                for item in s["precise"]:
                    if item["seg_id"] == msg.get("seg_id") and any(t["label"] == msg.get("label") for t in item["topk"]):
                        item["chosen"], item["uncertain"] = msg["label"], False
                self._rebuild_precise_draft()
            elif kind == "sign.remove":
                s["precise"] = [i for i in s["precise"] if i["seg_id"] != msg.get("seg_id")]
                self._rebuild_precise_draft()
            elif kind == "draft.edit":
                s["draft"]["text"] = str(msg.get("text", ""))[:500]
                s["draft"]["edited"] = True
            elif kind == "draft.confirm":
                if not s["draft"]["text"].strip():
                    return
                metrics.log("draft.confirm", source=s["draft"]["source"], edited=s["draft"]["edited"],
                            candidate=s["natural"]["selected"] if s["natural"] else None,
                            low_confidence=s["natural"]["low_confidence"] if s["natural"] else None,
                            signs=[i["chosen"] for i in s["precise"] if i["chosen"]])
                s["messages"].append({"id": self._id(), "text": s["draft"]["text"].strip(), "source": s["draft"]["source"],
                                      "edited": s["draft"]["edited"], "t": time.time(),
                                      "glosses": [i["chosen"] for i in s["precise"] if i["chosen"]]})
                self._clear_draft()
            elif kind == "draft.clear":
                self._clear_draft()
            elif kind == "sign.start":
                if self.on_sign_start:
                    self.on_sign_start()
                return
            elif kind == "sign.done":
                if self.on_sign_done:
                    self.on_sign_done()
                return
            elif kind == "caption.correct":
                for c in s["captions"]:
                    if c["id"] == msg.get("id") and str(msg.get("text", "")).strip():
                        c["original"] = c["original"] or c["text"]
                        c["text"] = str(msg["text"]).strip()[:500]
                        if self.on_final_caption:
                            self.on_final_caption(c["id"], c["text"])
            elif kind in ("asr.pause", "asr.resume"):
                paused = kind == "asr.pause"
                s["asr"]["state"] = "paused" if paused else "listening"
                if self.on_asr_pause:
                    self.on_asr_pause(paused)
            elif kind == "session.end":
                self.state = _fresh(s["sign"]["mode"], s["asr"]["state"])
            self._publish()
