import pytest


def literal(labels):
    return " ".join(labels).capitalize() + ".", "precise-literal"


@pytest.fixture
def hub():
    from medbridge.hub import Hub

    sent = []
    h = Hub(broadcast=sent.append, translate=literal, precise_threshold=0.3, natural_min_score=-1.0)
    h.state["sign"]["mode"] = "any"  # engine-event tests below are mode-agnostic unless they set a mode
    h.sent = sent
    return h


def sentence(seg_id, texts_scores):
    return {"seg_id": seg_id, "latency_ms": 900,
            "candidates": [{"text": t, "score": s, "rel_score": 1 / len(texts_scores)} for t, s in texts_scores]}


def test_final_caption_replaces_interim_and_is_stored(hub):
    hub.on_caption("interim", 0, "Are you exper")
    assert hub.state["interim"] == {"id": 0, "text": "Are you exper"}
    hub.on_caption("final", 0, "Are you experiencing chest pain?")
    assert hub.state["interim"] is None
    assert hub.state["captions"][-1]["text"] == "Are you experiencing chest pain?"


def test_doctor_correction_keeps_original_text(hub):
    hub.on_caption("final", 0, "Are you allergic to pencil in?")
    cid = hub.state["captions"][0]["id"]
    hub.apply({"type": "caption.correct", "id": cid, "text": "Are you allergic to penicillin?"}, role="doctor")
    cap = hub.state["captions"][0]
    assert cap["text"] == "Are you allergic to penicillin?"
    assert cap["original"] == "Are you allergic to pencil in?"


def test_natural_sentence_preselects_top_candidate_then_patient_picks(hub):
    hub.on_sentence(sentence(1, [("My stomach hurts.", -0.4), ("My stomach is hurt.", -0.6), ("I have pain.", -0.9)]))
    assert hub.state["draft"]["text"] == "My stomach hurts."
    assert hub.state["draft"]["source"] == "natural"
    hub.apply({"type": "candidate.pick", "index": 2}, role="patient")
    assert hub.state["draft"]["text"] == "I have pain."
    assert hub.state["natural"]["selected"] == 2


def test_natural_low_score_is_flagged(hub):
    hub.on_sentence(sentence(1, [("Something odd.", -1.8), ("Other.", -2.0), ("Else.", -2.2)]))
    assert hub.state["natural"]["low_confidence"] is True


def test_confirm_moves_draft_to_messages_and_clears_draft(hub):
    hub.on_sentence(sentence(1, [("My stomach hurts.", -0.4), ("b", -0.6), ("c", -0.9)]))
    hub.apply({"type": "draft.confirm"}, role="patient")
    msg = hub.state["messages"][-1]
    assert msg["text"] == "My stomach hurts." and msg["source"] == "natural" and msg["edited"] is False
    assert hub.state["draft"]["text"] == "" and hub.state["natural"] is None


def test_confirm_with_empty_draft_does_nothing(hub):
    hub.apply({"type": "draft.confirm"}, role="patient")
    assert hub.state["messages"] == []


def test_precise_predictions_build_english_from_chosen_labels(hub):
    hub.on_sign_prediction(1, [{"label": "stomach", "glosses": ["STOMACH"], "p": 0.8}])
    hub.on_sign_prediction(2, [{"label": "hurt", "glosses": ["HURT"], "p": 0.7}])
    assert [i["chosen"] for i in hub.state["precise"]] == ["stomach", "hurt"]
    assert hub.state["draft"] == {"text": "Stomach hurt.", "source": "precise-literal", "edited": False}


def test_uncertain_precise_prediction_waits_for_patient_pick(hub):
    hub.on_sign_prediction(1, [{"label": "dizzy", "glosses": ["DIZZY"], "p": 0.2},
                               {"label": "sick", "glosses": ["SICK"], "p": 0.15}])
    item = hub.state["precise"][0]
    assert item["uncertain"] is True and item["chosen"] is None
    assert hub.state["draft"]["text"] == ""
    hub.apply({"type": "sign.pick", "seg_id": 1, "label": "sick"}, role="patient")
    assert hub.state["precise"][0]["chosen"] == "sick"
    assert hub.state["draft"]["text"] == "Sick."


def test_sign_remove_drops_item(hub):
    hub.on_sign_prediction(1, [{"label": "yes", "glosses": ["YES"], "p": 0.9}])
    hub.apply({"type": "sign.remove", "seg_id": 1}, role="patient")
    assert hub.state["precise"] == [] and hub.state["draft"]["text"] == ""


def test_patient_edit_marks_draft_edited(hub):
    hub.on_sentence(sentence(1, [("My stomach hurt.", -0.4), ("b", -0.6), ("c", -0.9)]))
    hub.apply({"type": "draft.edit", "text": "My stomach hurts."}, role="patient")
    hub.apply({"type": "draft.confirm"}, role="patient")
    assert hub.state["messages"][-1]["edited"] is True


def test_mode_switch_clears_draft_and_notifies_vision():
    from medbridge.hub import Hub

    modes = []
    h = Hub(broadcast=lambda m: None, translate=literal, on_mode=modes.append)
    h.on_sign_prediction(1, [{"label": "yes", "glosses": ["YES"], "p": 0.9}])
    h.apply({"type": "mode.set", "mode": "natural"}, role="patient")
    assert h.state["sign"]["mode"] == "natural" and h.state["precise"] == []
    assert modes == ["natural"]


def test_mode_set_to_a_mode_the_server_does_not_run_is_ignored():
    from medbridge.hub import Hub

    modes = []
    h = Hub(broadcast=lambda m: None, translate=literal, on_mode=modes.append, modes=("precise",))
    h.state["sign"]["mode"] = "precise"
    h.apply({"type": "mode.set", "mode": "natural"}, role="patient")
    assert h.state["sign"]["mode"] == "precise" and modes == []


def test_roles_are_enforced(hub):
    hub.on_sentence(sentence(1, [("My stomach hurts.", -0.4), ("b", -0.6), ("c", -0.9)]))
    hub.apply({"type": "draft.confirm"}, role="doctor")
    assert hub.state["messages"] == []
    hub.on_caption("final", 0, "Hello")
    hub.apply({"type": "caption.correct", "id": hub.state["captions"][0]["id"], "text": "Hi"}, role="patient")
    assert hub.state["captions"][0]["text"] == "Hello"


def test_session_end_clears_conversation(hub):
    hub.on_caption("final", 0, "Hello")
    hub.on_sentence(sentence(1, [("Hi.", -0.4), ("b", -0.6), ("c", -0.9)]))
    hub.apply({"type": "draft.confirm"}, role="patient")
    hub.apply({"type": "session.end"}, role="doctor")
    assert hub.state["captions"] == [] and hub.state["messages"] == []


def test_state_changes_are_broadcast_as_snapshots(hub):
    hub.on_caption("final", 0, "Hello")
    assert hub.sent[-1]["type"] == "state"
    assert hub.sent[-1]["state"]["captions"][0]["text"] == "Hello"


def test_late_sentence_after_switch_to_precise_is_ignored(hub):
    hub.apply({"type": "mode.set", "mode": "precise"}, role="patient")
    hub.on_sentence(sentence(1, [("My stomach hurts.", -0.4), ("b", -0.6), ("c", -0.9)]))
    assert hub.state["natural"] is None and hub.state["draft"]["text"] == ""


def test_sign_recognition_switch_drops_signs_while_off_and_tells_vision(hub):
    hub.apply({"type": "mode.set", "mode": "precise"}, role="patient")
    calls = []
    hub.on_sign_enable = calls.append
    hub.on_sign_status("signing")
    hub.apply({"type": "sign.enable", "on": False}, role="patient")
    assert hub.state["sign"]["enabled"] is False and hub.state["sign"]["state"] == "idle"
    hub.on_sign_prediction(1, [{"label": "yes", "glosses": ["YES"], "p": 0.9}])
    assert hub.state["precise"] == [] and hub.state["draft"]["text"] == ""
    hub.apply({"type": "sign.enable", "on": True}, role="patient")
    hub.on_sign_prediction(2, [{"label": "yes", "glosses": ["YES"], "p": 0.9}])
    assert [i["chosen"] for i in hub.state["precise"]] == ["yes"]
    assert calls == [False, True]


def test_sign_recognition_switch_is_patient_only_survives_session_end_and_ignores_bad_values(hub):
    hub.apply({"type": "sign.enable", "on": False}, role="doctor")
    hub.apply({"type": "sign.enable", "on": "no"}, role="patient")
    assert hub.state["sign"]["enabled"] is True
    hub.apply({"type": "sign.enable", "on": False}, role="patient")
    hub.apply({"type": "session.end"}, role="doctor")
    assert hub.state["sign"]["enabled"] is False


def test_late_sign_after_switch_to_natural_is_ignored(hub):
    hub.apply({"type": "mode.set", "mode": "natural"}, role="patient")
    hub.on_sign_prediction(1, [{"label": "yes", "glosses": ["YES"], "p": 0.9}])
    assert hub.state["precise"] == []


def test_malformed_candidate_pick_is_ignored(hub):
    hub.on_sentence(sentence(1, [("A.", -0.4), ("B.", -0.6), ("C.", -0.9)]))
    hub.apply({"type": "candidate.pick", "index": "two"}, role="patient")
    assert hub.state["natural"]["selected"] == 0


def test_async_interim_text_matches_literal_translator():
    import threading

    from medbridge.hub import Hub

    gate = threading.Event()

    def slow(labels):
        gate.wait(5)
        return "I hurt.", "precise-llm"

    h = Hub(broadcast=lambda m: None, translate=slow, async_translate=True)
    h.state["sign"]["mode"] = "precise"
    h.on_sign_prediction(1, [{"label": "me / I", "glosses": ["ME"], "p": 0.9}])
    assert h.state["draft"]["text"] == "Me."
    gate.set()


def with_phrases(seg_id, phrases, free):
    return {"seg_id": seg_id, "latency_ms": 700,
            "phrases": [{"text": t, "score": s, "rel_score": 0.3} for t, s in phrases],
            "candidates": [{"text": t, "score": s, "rel_score": 0.4} for t, s in free]}


def test_bank_phrases_come_first_then_the_free_translation(hub):
    hub.on_sentence(with_phrases(1, [("My stomach hurts.", -0.8), ("I feel sick.", -1.1), ("I need water.", -1.4)],
                                 [("He was heartbroken.", -0.6), ("He was hurt.", -0.7), ("x", -0.9)]))
    n = hub.state["natural"]
    assert [c["kind"] for c in n["candidates"]] == ["phrase", "phrase", "phrase", "free"]
    assert n["candidates"][3]["text"] == "He was heartbroken."
    assert hub.state["draft"] == {"text": "My stomach hurts.", "source": "natural-phrase", "edited": False}


def test_picking_the_free_translation_marks_source_natural(hub):
    hub.on_sentence(with_phrases(1, [("A.", -0.8), ("B.", -1.1), ("C.", -1.4)], [("Free.", -0.6)]))
    assert hub.state["draft"]["source"] == "natural-phrase"  # a bank phrase is preselected
    hub.apply({"type": "candidate.pick", "index": 3}, role="patient")
    assert hub.state["draft"]["source"] == "natural" and hub.state["draft"]["text"] == "Free."


def test_low_confidence_uses_top_phrase_score_when_phrases_present():
    from medbridge.hub import Hub

    h = Hub(broadcast=lambda m: None, translate=literal, natural_min_score=-0.65, phrase_min_score=-1.5)
    h.on_sentence(with_phrases(1, [("A.", -1.2), ("B.", -1.6), ("C.", -1.9)], [("Free.", -2.0)]))
    assert h.state["natural"]["low_confidence"] is False
    h.on_sentence(with_phrases(2, [("A.", -1.7), ("B.", -1.8), ("C.", -1.9)], [("Free.", -0.1)]))
    assert h.state["natural"]["low_confidence"] is True



def test_sign_start_from_patient_reaches_vision():
    from medbridge.hub import Hub

    started = []
    h = Hub(broadcast=lambda m: None, translate=literal, on_sign_start=lambda: started.append(1))
    h.apply({"type": "sign.start"}, role="doctor")
    h.apply({"type": "sign.start"}, role="patient")
    assert started == [1]


def test_final_and_corrected_captions_are_sent_for_signing():
    from medbridge.hub import Hub

    sent = []
    h = Hub(broadcast=lambda m: None, translate=literal, on_final_caption=lambda cid, text: sent.append((cid, text)))
    h.on_caption("interim", 0, "Are you")
    h.on_caption("final", 0, "Are you in pain?")
    cid = h.state["captions"][0]["id"]
    h.apply({"type": "caption.correct", "id": cid, "text": "Are you in pain now?"}, role="doctor")
    assert sent == [(cid, "Are you in pain?"), (cid, "Are you in pain now?")]


def test_typed_caption_from_the_doctor_is_stored_and_sent_for_signing():
    from medbridge.hub import Hub

    signed = []
    h = Hub(broadcast=lambda m: None, translate=literal, on_final_caption=lambda cid, text: signed.append(text))
    h.apply({"type": "caption.add", "text": "  Please lie down.  "}, role="doctor")
    h.apply({"type": "caption.add", "text": "   "}, role="doctor")
    h.apply({"type": "caption.add", "text": "Not from the patient."}, role="patient")
    assert [c["text"] for c in h.state["captions"]] == ["Please lie down."]
    assert h.state["captions"][0]["original"] is None and signed == ["Please lie down."]


def test_interim_captions_are_offered_for_fetching_signs_early(hub):
    seen = []
    hub.on_interim_caption = seen.append
    hub.on_caption("interim", 0, "Are you")
    hub.on_caption("final", 0, "Are you in pain?")
    assert seen == ["Are you"]


def test_signing_status_is_published_in_state(hub):
    hub.on_signing({"caption_id": 3, "status": "ready", "frames": 90, "fps": 30,
                    "words": [{"word": "pain", "gloss": "PAIN", "source": "aslc", "start": 0, "end": 40}]})
    assert hub.state["signing"]["caption_id"] == 3 and hub.state["signing"]["status"] == "ready"
    assert hub.sent[-1]["state"]["signing"]["words"][0]["gloss"] == "PAIN"


def test_pausing_captions_drops_the_live_text_and_ignores_late_captions(hub):
    paused = []
    hub.on_asr_pause = paused.append
    hub.on_caption("interim", 0, "Are you exper")

    hub.apply({"type": "asr.pause"}, role="doctor")
    assert paused == [True]
    assert hub.state["interim"] is None
    hub.on_caption("interim", 0, "Are you experiencing")  # heard before the pause, transcribed after it
    hub.on_caption("final", 0, "Are you experiencing chest pain?")
    assert hub.state["interim"] is None and hub.state["captions"] == []

    hub.apply({"type": "asr.resume"}, role="doctor")
    assert paused == [True, False]
    hub.on_caption("final", 1, "Where does it hurt?")
    assert [c["text"] for c in hub.state["captions"]] == ["Where does it hurt?"]
