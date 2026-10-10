import base64
from types import SimpleNamespace

import numpy as np
import pytest

GLOSSES = ["YOU", "YOUR", "FEEL", "PAIN", "HURT", "DOCTOR1", "DOCTOR2", "W.H.A.T", "WHAT1", "WHAT2", "MEDICINE",
           "SEVEN", "THANKYOU", "ME", "HELLO", "OK", "HE"]


def test_lexicon_prefers_plain_lowest_variant():
    from medbridge.text2sign import build_lexicon

    lex = build_lexicon(GLOSSES)
    assert lex["doctor"] == "DOCTOR1"
    assert lex["what"] == "WHAT1"


def test_text_to_glosses_skips_unsigned_words_and_maps_forms():
    from medbridge.text2sign import build_lexicon, text_to_glosses

    lex = build_lexicon(GLOSSES)
    out = text_to_glosses("Are you experiencing chest pain?", lex)
    assert out == [("you", "YOU"), ("experiencing", "FEEL"), ("chest", None), ("pain", "PAIN")]
    assert text_to_glosses("It hurts, take 7 medications. Thank you, doctor!", lex) == [
        ("hurts", "HURT"), ("take", None), ("7", "SEVEN"), ("medications", "MEDICINE"), ("thank you", "THANKYOU"),
        ("doctor", "DOCTOR1")]
    assert text_to_glosses("Hi, I'm okay", lex) == [("hi", "HELLO"), ("i'm", "ME"), ("okay", "OK")]


def lm(n, x, y, z=0.0):
    return SimpleNamespace(landmark=[SimpleNamespace(x=x, y=y, z=z) for _ in range(n)])


def test_holistic_frame_uses_shared_178_point_layout():
    from medbridge.text2sign import FACE_IDX, holistic_frame

    pose = lm(33, 0.5, 0.5)
    pose.landmark[11] = SimpleNamespace(x=0.6, y=0.5, z=0.0)  # person's left shoulder
    res = SimpleNamespace(pose_landmarks=pose, face_landmarks=lm(468, 0.5, 0.3), left_hand_landmarks=None,
                          right_hand_landmarks=lm(21, 0.4, 0.7, 0.01))
    f = holistic_frame(res, 100, 50)
    assert f.shape == (178, 3) and len(FACE_IDX) == 128
    assert f[0].tolist() == pytest.approx([60, 25, 0])          # LEFT_SHOULDER in pixels
    assert np.isnan(f[136:157]).all()                           # LEFT_HAND missing
    assert f[157, :2].tolist() == pytest.approx([40, 35])        # RIGHT_HAND wrist


def test_normalize_centres_shoulders_and_sets_unit_width():
    from medbridge.text2sign import normalize

    seq = np.full((4, 178, 3), np.nan, np.float32)
    seq[:, 0] = [300, 200, 10]   # left shoulder
    seq[:, 1] = [100, 200, 10]   # right shoulder
    seq[:, 157] = [200, 300, 10]
    out = normalize(seq)
    assert out[0, 0].tolist() == pytest.approx([0.5, 0, 0]) and out[0, 1].tolist() == pytest.approx([-0.5, 0, 0])
    assert out[0, 157].tolist() == pytest.approx([0, 0.5, 0])


def test_resample_changes_frame_rate_and_keeps_endpoints():
    from medbridge.text2sign import resample

    seq = np.zeros((26, 178, 3), np.float32)
    seq[:, 0, 0] = np.arange(26)
    out = resample(seq, 25, 30)
    assert len(out) == 31
    assert out[0, 0, 0] == 0 and out[-1, 0, 0] == pytest.approx(25)


def test_assemble_adds_transitions_and_holds_for_missing_words():
    from medbridge.text2sign import assemble

    a = np.zeros((10, 178, 3), np.float32)
    b = np.ones((12, 178, 3), np.float32)
    motion, timeline = assemble([("you", "YOU", "aslc", a), ("chest", None, "none", None), ("pain", "PAIN", "signmt", b)],
                                transition=8, hold=18)
    assert [w["source"] for w in timeline] == ["aslc", "none", "signmt"]
    assert timeline[0]["start"] == 0 and timeline[0]["end"] == 10
    assert timeline[1]["end"] - timeline[1]["start"] == 18
    assert timeline[2]["start"] == timeline[1]["end"] + 8 and timeline[2]["end"] == len(motion)
    mid = motion[timeline[2]["start"] - 4, 0, 0]
    assert 0 < mid < 1   # interpolated transition into the next sign


def test_payload_round_trips_float32_motion():
    from medbridge.text2sign import payload

    motion = np.arange(2 * 178 * 3, dtype=np.float32).reshape(2, 178, 3)
    p = payload(7, motion, [{"word": "you"}], fps=30)
    back = np.frombuffer(base64.b64decode(p["data"]), dtype=np.float32).reshape(p["frames"], p["points"], 3)
    assert p["caption_id"] == 7 and np.array_equal(back, motion)


def test_builder_uses_dictionary_then_signmt_then_text():
    from medbridge.text2sign import Builder, build_lexicon

    clip = np.zeros((20, 178, 3), np.float32)
    clip[:, 0] = [300, 200, 0]; clip[:, 1] = [100, 200, 0]
    calls = []

    class Dict:
        def get(self, gloss):
            return clip if gloss == "YOU" else None

    class SignMT:
        def get(self, word):
            calls.append(word)
            return (clip, 30) if word == "chest" else None

    b = Builder(build_lexicon(GLOSSES), Dict(), SignMT())
    motion, timeline = b.build("Are you okay? Chest pain")
    assert [(w["word"], w["source"]) for w in timeline] == [("you", "aslc"), ("okay", "none"), ("chest", "signmt"), ("pain", "none")]
    assert calls == ["okay", "chest", "pain"]   # only words missing from the local dictionary leave the Mac
    assert motion.shape[1:] == (178, 3)
