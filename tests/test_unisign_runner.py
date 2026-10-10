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
