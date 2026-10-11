import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "data/src/ASL-citizen-code/ST-GCN/asl_citizen_dataset_pose.py"
WEIGHTS = ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt"


def _upstream_getitem(tmp_path, data):
    """Run the original ASLCitizen.__getitem__ on one saved pose array."""
    if not UPSTREAM.exists():
        pytest.skip("upstream ASL Citizen source not fetched")
    ns = {}
    exec(compile(UPSTREAM.read_text(), str(UPSTREAM), "exec"), ns)
    ds = object.__new__(ns["ASLCitizen"])
    np.save(tmp_path / "clip.npy", data)
    ds.max_frames, ds.transforms = 128, None
    ds.pose_paths, ds.labels = [str(tmp_path / "clip.npy")], [0]
    ds.gloss_dict, ds.video_info = {"A": 0}, [["u", "f", "A"]]
    return ds[0][0]


@pytest.mark.parametrize("T", [90, 200])
def test_preprocess_matches_upstream_getitem(tmp_path, T):
    from medbridge.islr import preprocess

    rng = np.random.default_rng(T)
    data = rng.uniform(0, 1, size=(T, 543, 2))
    data[5:9, 33:54] = 0  # a few frames with the right hand missing
    ref = _upstream_getitem(tmp_path, data)
    ours = preprocess(data)
    assert ours.shape == (1, 2, 128, 27)
    assert torch.allclose(ours[0].double(), ref, atol=1e-5)


def test_load_gloss_list_is_sorted_unique_stripped(tmp_path):
    from medbridge.islr import load_gloss_list

    csv = tmp_path / "train.csv"
    csv.write_text("Participant ID,Video file,Gloss,ASL-LEX Code\nP1,a.mp4,ZEBRA ,x\nP2,b.mp4,APPLE,y\nP1,c.mp4,ZEBRA,x\n")
    assert load_gloss_list(csv) == ["APPLE", "ZEBRA"]


def test_topk_restricts_to_vocab_and_merges_variants():
    from medbridge.islr import topk

    glosses = ["APPLE", "DOCTOR1", "DOCTOR2", "HURT", "ZEBRA"]
    logits = torch.tensor([10.0, 1.0, 1.0, 1.5, 9.0])
    vocab = {"DOCTOR1": "doctor", "DOCTOR2": "doctor", "HURT": "hurt / pain"}
    out = topk(logits, glosses, vocab, k=5)
    assert [o["label"] for o in out] == ["doctor", "hurt / pain"]
    assert sum(o["p"] for o in out) == pytest.approx(1.0)
    assert out[0]["glosses"] == ["DOCTOR1", "DOCTOR2"]


def test_topk_full_vocab_uses_gloss_as_label():
    from medbridge.islr import topk

    out = topk(torch.tensor([0.0, 3.0]), ["APPLE", "ZEBRA"], None, k=1)
    assert out == [{"label": "ZEBRA", "glosses": ["ZEBRA"], "p": pytest.approx(0.9526, abs=1e-3)}]


@pytest.mark.skipif(not WEIGHTS.exists(), reason="ASL Citizen weights not downloaded")
def test_model_loads_weights_strictly():
    from medbridge.islr import load_stgcn

    model = load_stgcn(WEIGHTS, n_classes=2731)
    assert not model.training
    out = model(torch.zeros(1, 2, 128, 27))
    assert out.shape == (1, 2731)


def test_holistic_to_array_layout():
    from medbridge.islr import holistic_to_array

    lm = lambda n, v: SimpleNamespace(landmark=[SimpleNamespace(x=v, y=v + 0.01) for _ in range(n)])
    res = SimpleNamespace(pose_landmarks=lm(33, 0.1), right_hand_landmarks=lm(21, 0.2),
                          left_hand_landmarks=None, face_landmarks=lm(468, 0.4))
    a = holistic_to_array(res)
    assert a.shape == (543, 2)
    assert a[0].tolist() == pytest.approx([0.1, 0.11])
    assert a[33].tolist() == pytest.approx([0.2, 0.21])
    assert not a[54:75].any()
    assert a[75].tolist() == pytest.approx([0.4, 0.41])
