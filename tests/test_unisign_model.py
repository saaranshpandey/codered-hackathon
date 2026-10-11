from pathlib import Path

import pytest

CKPT = Path(__file__).resolve().parents[1] / "data/models/openasl_pose_only_slt.pth"


@pytest.mark.skipif(not CKPT.exists(), reason="Uni-Sign checkpoint not downloaded")
def test_pose_only_model_loads_checkpoint_strictly():
    from medbridge.unisign.model import load_unisign

    model, report = load_unisign(CKPT, lang="English", device="cpu")
    assert report.missing_keys == []
    assert report.unexpected_keys == []
    assert not model.training


POSES = sorted((CKPT.parents[1] / "eval/poses/lightweight_mps").glob("*.npz"))


@pytest.mark.skipif(not CKPT.exists() or not POSES, reason="checkpoint or cached eval poses missing")
def test_rank_scores_bank_phrases_and_prefers_the_models_own_translation():
    import numpy as np

    from medbridge.unisign.model import load_unisign
    from medbridge.unisign.preprocess import build_src_input

    model, _ = load_unisign(CKPT, lang="English", device="cpu")
    z = np.load(POSES[0])
    src = build_src_input(list(z["k"]), list(z["s"]))
    own = model.translate(src)[0][0]
    bank = ["I need the bathroom.", own, "My stomach hurts."]
    ranked = model.rank(src, bank)
    assert sorted(p for p, _ in ranked) == sorted(bank)
    assert ranked[0][0] == own
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True) and all(s <= 0 for s in scores)
