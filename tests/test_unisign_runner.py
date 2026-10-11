import numpy as np
import pytest


def test_select_person_picks_largest_visible_person():
    from medbridge.unisign_runner import select_person

    small = np.zeros((133, 2)); small[:, 0] = np.linspace(0.40, 0.45, 133); small[:, 1] = np.linspace(0.40, 0.45, 133)
    big = np.zeros((133, 2)); big[:, 0] = np.linspace(0.10, 0.90, 133); big[:, 1] = np.linspace(0.10, 0.90, 133)
    kps = np.stack([small, big]); scores = np.ones((2, 133))
    k, s = select_person(kps, scores)
    assert k.shape == (1, 133, 2) and s.shape == (1, 133)
    assert np.array_equal(k[0], big)


def test_select_person_returns_zeros_when_nobody_detected():
    from medbridge.unisign_runner import select_person

    k, s = select_person(np.zeros((0, 133, 2)), np.zeros((0, 133)))
    assert k.shape == (1, 133, 2) and not k.any() and not s.any()


def test_rel_scores_are_softmax_in_input_order():
    from medbridge.unisign_runner import rel_scores

    r = rel_scores([-0.1, -0.5, -2.0])
    assert sum(r) == pytest.approx(1.0)
    assert r[0] > r[1] > r[2]


CLIPS = sorted((__import__("pathlib").Path(__file__).resolve().parents[1] / "data/eval/openasl").glob("*.mp4"))


@pytest.mark.skipif(not CLIPS, reason="OpenASL eval clips not fetched")
def test_coreml_pose_matches_cpu_pose():
    import cv2

    from medbridge.unisign_runner import make_pose

    cap = cv2.VideoCapture(str(CLIPS[0]))
    frames = [cap.read()[1] for _ in range(10)]
    cpu, coreml = make_pose("lightweight", "cpu"), make_pose("lightweight", "mps")
    for f in frames:
        (kc, sc), (km, sm) = cpu(f), coreml(f)
        h, w = f.shape[:2]
        assert kc.shape == km.shape == (len(kc), 133, 2)
        visible = (sc[0] > 0.5) & (sm[0] > 0.5)
        err = np.abs(kc[0][visible] - km[0][visible]) / np.array([w, h])
        assert err.max() < 0.01  # under 1% of the frame


def test_largest_box_keeps_only_the_biggest_person_box():
    from medbridge.unisign_runner import largest_box

    boxes = np.array([[0, 0, 10, 10], [0, 0, 100, 50], [5, 5, 20, 20]], dtype=float)
    assert largest_box(boxes).tolist() == [[0, 0, 100, 50]]
    assert len(largest_box(np.zeros((0, 4)))) == 0


def test_top_phrases_returns_k_best_with_share_of_whole_bank():
    from medbridge.unisign_runner import top_phrases

    ranked = [("A.", -0.2), ("B.", -0.9), ("C.", -1.5), ("D.", -3.0)]
    out = top_phrases(ranked, k=3)
    assert [p["text"] for p in out] == ["A.", "B.", "C."]
    assert out[0]["rel_score"] > out[1]["rel_score"] > out[2]["rel_score"]
    assert sum(p["rel_score"] for p in out) < 1.0  # share of the whole bank, not just the top 3


CKPT = __import__("pathlib").Path(__file__).resolve().parents[1] / "data/models/openasl_pose_only_slt.pth"
POSES = sorted((CKPT.parents[1] / "eval/poses/lightweight_mps").glob("*.npz"))


@pytest.mark.skipif(not CKPT.exists() or not POSES, reason="checkpoint or cached eval poses missing")
def test_translate_returns_top3_bank_phrases_and_free_translation():
    from medbridge.unisign_runner import NaturalSigner

    bank = ["I need water.", "My stomach hurts.", "I feel dizzy.", "Yes.", "No."]
    signer = NaturalSigner(CKPT, device="cpu", pose_device="cpu", phrases=bank)
    z = np.load(POSES[0])
    out = signer.translate(list(z["k"]), list(z["s"]))
    assert len(out["candidates"]) == 3
    assert len(out["phrases"]) == 3 and all(p["text"] in bank for p in out["phrases"])
