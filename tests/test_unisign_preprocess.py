import ast
from pathlib import Path

import numpy as np
import pytest
import torch

UPSTREAM = Path(__file__).resolve().parents[1] / "data/src/Uni-Sign/datasets.py"


def _upstream_fns():
    """Load load_part_kp/crop_scale straight from the upstream Uni-Sign source."""
    if not UPSTREAM.exists():
        pytest.skip("upstream Uni-Sign source not fetched")
    tree = ast.parse(UPSTREAM.read_text())
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("load_part_kp", "crop_scale")]
    ns = {"np": np, "torch": torch, "copy": __import__("copy")}
    exec(compile(ast.Module(body=fns, type_ignores=[]), str(UPSTREAM), "exec"), ns)
    return ns["load_part_kp"]


def _random_pose(T, seed=0):
    rng = np.random.default_rng(seed)
    skeletons = [rng.uniform(0.2, 0.8, size=(1, 133, 2)) for _ in range(T)]
    confs = [rng.uniform(0.0, 1.0, size=(1, 133)) for _ in range(T)]
    return skeletons, confs


def test_load_part_kp_matches_upstream():
    from medbridge.unisign.preprocess import load_part_kp

    skeletons, confs = _random_pose(40)
    ours = load_part_kp(skeletons, confs)
    ref = _upstream_fns()(skeletons, confs, force_ok=True)
    assert ours.keys() == ref.keys()
    for k in ref:
        assert torch.equal(ours[k], ref[k]), k


def test_sample_indices_keeps_all_frames_when_short():
    from medbridge.unisign.preprocess import sample_indices

    assert sample_indices(10, 256).tolist() == list(range(10))


def test_sample_indices_returns_sorted_unique_subset_when_long():
    from medbridge.unisign.preprocess import sample_indices

    idx = sample_indices(400, 256)
    assert len(idx) == 256
    assert len(set(idx.tolist())) == 256
    assert idx.tolist() == sorted(idx.tolist())
    assert idx.min() >= 0 and idx.max() < 400


def test_build_src_input_shapes_and_mask():
    from medbridge.unisign.preprocess import build_src_input

    skeletons, confs = _random_pose(30)
    src = build_src_input(skeletons, confs, max_length=256)
    assert src["body"].shape == (1, 30, 9, 3)
    assert src["left"].shape == (1, 30, 21, 3)
    assert src["right"].shape == (1, 30, 21, 3)
    assert src["face_all"].shape == (1, 30, 18, 3)
    assert src["attention_mask"].tolist() == [[1] * 30]
