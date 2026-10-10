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
