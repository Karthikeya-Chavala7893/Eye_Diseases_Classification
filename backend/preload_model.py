"""
backend/preload_model.py
────────────────────────
Build-time model pre-download script for Render deployment.

Run during `pip install` / build phase so the ensemble_classifier.pth
checkpoint is already on disk when Gunicorn starts. This eliminates the
60-90 second HuggingFace download that would otherwise happen on every
cold start, reducing total startup latency from ~5 minutes to ~90 seconds.

Usage (Render Build Command):
    pip install -r requirements.txt && python preload_model.py

Environment variables:
    HF_MODEL_REPO  — HuggingFace repo ID (e.g. Karthikeya-Chavala7893/visionai-retinal-ensemble)
    HF_TOKEN       — optional HF token for private repos
    LOCAL_MODEL_ID — override download target path (default: models/ensemble_classifier.pth)
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("preload_model")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def preload() -> None:
    hf_repo = os.environ.get("HF_MODEL_REPO", "").strip()
    if not hf_repo:
        logger.warning(
            "HF_MODEL_REPO not set — skipping model pre-download. "
            "The model will be downloaded at first request (slower cold start)."
        )
        return

    models_dir = os.path.join(BASE_DIR, "models")
    local_path = os.path.join(models_dir, "ensemble_classifier.pth")

    if os.path.isfile(local_path):
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        logger.info(
            "Model already cached at %s (%.1f MB) — skipping download.", local_path, size_mb
        )
        return

    logger.info("Pre-downloading ensemble checkpoint from HuggingFace: %s ...", hf_repo)
    os.makedirs(models_dir, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download

        token = os.environ.get("HF_TOKEN") or None
        downloaded = hf_hub_download(
            repo_id=hf_repo,
            filename="ensemble_classifier.pth",
            local_dir=models_dir,
            token=token,
        )
        size_mb = os.path.getsize(downloaded) / (1024 * 1024)
        logger.info(
            "✓ Model pre-downloaded successfully: %s (%.1f MB)", downloaded, size_mb
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to pre-download model from '%s': %s\n"
            "The server will attempt to download it at first request instead.",
            hf_repo,
            exc,
        )
        # Don't fail the build — the runtime download fallback will handle it.
        sys.exit(0)


if __name__ == "__main__":
    preload()
