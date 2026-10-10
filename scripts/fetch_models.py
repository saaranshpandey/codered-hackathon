"""Download everything the app needs (idempotent, ~3 GB):

  data/models/openasl_pose_only_slt.pth        Uni-Sign pose-only, OpenASL fine-tuned (HF ZechengLi19/Uni-Sign)
  google/mt5-base config + tokenizer            (HF cache; weights come from the Uni-Sign checkpoint)
  data/models/aslc_stgcn/...weights.pt          ASL Citizen ST-GCN (github.com/microsoft/ASL-citizen-code, MIT)
  data/aslc/ASL_Citizen/splits/*.csv            gloss index (range-read from the 42.8 GB dataset zip)
  mlx-community/whisper-large-v3-turbo          (HF cache)
  rtmlib Wholebody ONNX models                  (downloaded by rtmlib on first use)

Also clones the upstream repos into data/src/ (used by the parity tests and eval scripts).
"""
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download
from remotezip import RemoteZip

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "data/models"
ASLC_ZIP = "https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"
STGCN_ZIP = "https://github.com/microsoft/ASL-citizen-code/releases/download/checkpoints_v1/ASL_citizen_stgcn_weights.zip"


def main():
    MODELS.mkdir(parents=True, exist_ok=True)

    print("Uni-Sign checkpoint…")
    hf_hub_download("ZechengLi19/Uni-Sign", "openasl_pose_only_slt.pth", local_dir=MODELS)

    print("mT5-base config + tokenizer…")
    snapshot_download("google/mt5-base", allow_patterns=["*.json", "spiece.model"])

    weights = MODELS / "aslc_stgcn/ASL_citizen_stgcn_weights.pt"
    if not weights.exists():
        print("ASL Citizen ST-GCN weights…")
        z = MODELS / "ASL_citizen_stgcn_weights.zip"
        urllib.request.urlretrieve(STGCN_ZIP, z)
        zipfile.ZipFile(z).extractall(MODELS / "aslc_stgcn")

    splits = ROOT / "data/aslc/ASL_Citizen/splits"
    if not (splits / "train.csv").exists():
        print("ASL Citizen split CSVs (range read)…")
        with RemoteZip(ASLC_ZIP) as zf:
            for name in ("train", "val", "test"):
                zf.extract(f"ASL_Citizen/splits/{name}.csv", ROOT / "data/aslc")

    print("Whisper large-v3-turbo (MLX)…")
    snapshot_download("mlx-community/whisper-large-v3-turbo")

    src = ROOT / "data/src"
    src.mkdir(parents=True, exist_ok=True)
    for url in ("https://github.com/ZechengLi19/Uni-Sign.git", "https://github.com/microsoft/ASL-citizen-code.git"):
        target = src / url.rsplit("/", 1)[1].removesuffix(".git")
        if not target.exists():
            subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(target)], check=True)
    print("Done.")


if __name__ == "__main__":
    main()
