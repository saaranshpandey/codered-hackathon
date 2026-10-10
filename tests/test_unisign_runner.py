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
