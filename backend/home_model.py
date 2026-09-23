"""
backend/home_model.py
─────────────────────
Dedicated inference module for the Daily Home Mode image classifier.

Single Responsibility
─────────────────────
Load and own the NeuronZero/EyeDiseaseClassifier (or any compatible
``AutoModelForImageClassification``) model used exclusively by the home
screening path.  Exposes a single ``predict_home(image_bytes)`` function.

Design constraints:
  * MUST NOT import flask, firebase_admin, firestore or any HTTP library.
  * MUST NOT write to disk — images stay in ``io.BytesIO``.
  * MUST wrap every forward pass in ``torch.no_grad()``.
  * MUST handle PIL.Image.DecompressionBombError gracefully (return []).
  * MUST never raise on a bad image — return [] so the triage engine falls
    back to pixel cues.
  * Model is loaded ONCE per WSGI worker at startup, never per request.

Separation from ``model.py``
─────────────────────────────
``model.py`` owns the clinical RETFound pipeline and must not be modified.
If the clinical model happens to be the same HuggingFace checkpoint as the
home model (common during development), both modules load independently —
they share no state.  This isolation protects the clinical pipeline from
regressions when the home path evolves.
"""

import io
import logging
import time
import threading

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from config import Config

logger = logging.getLogger('visionai.home_model')

# ── Module-level singletons (one set per WSGI worker process) ────────────────
_processor = None
_model = None
_id2label: dict[int, str] = {}

#: True once both the processor and the model are initialised.
HOME_MODEL_LOADED: bool = False

#: Thread safety for lazy loading.
_load_lock = threading.Lock()

#: Percentage confidence values are rounded to this many decimal places.
_CONFIDENCE_DECIMALS = 2

#: Softmax is applied over the final logits axis.
_LOGITS_AXIS = -1


def load_home_model() -> None:
    """Initialise the home screening image processor and classifier.

    Loads the HuggingFace ``AutoModelForImageClassification`` identified by
    ``Config.HOME_MODEL_ID``.  Thread-safe: concurrent calls from multiple
    Gunicorn workers are serialised, and the second caller returns immediately
    once the first has completed.

    Raises:
        RuntimeError: If the weights cannot be loaded.  The caller (app.py)
            catches this and degrades gracefully — pixel cues are used instead.
    """
    global _processor, _model, _id2label, HOME_MODEL_LOADED

    with _load_lock:
        if HOME_MODEL_LOADED:
            logger.debug("load_home_model() called again — already initialised.")
            return

        started = time.monotonic()
        device = torch.device(Config.TORCH_DEVICE)
        model_id = Config.HOME_MODEL_ID
        logger.info(
            "Loading home screening model: %s (device=%s)", model_id, Config.TORCH_DEVICE
        )

        try:
            _processor = AutoImageProcessor.from_pretrained(model_id)
            _model = AutoModelForImageClassification.from_pretrained(model_id)
            _model.to(device)
            _model.eval()
            _id2label = {
                int(k): v
                for k, v in getattr(_model.config, 'id2label', {}).items()
            }
        except Exception as exc:  # noqa: BLE001 — re-raised as RuntimeError
            _processor = _model = None
            _id2label = {}
            HOME_MODEL_LOADED = False
            logger.error(
                "Failed to load home screening model '%s': %s",
                model_id, exc, exc_info=True,
            )
            raise RuntimeError(
                f"Home screening model initialisation failed: {exc}"
            ) from exc

        HOME_MODEL_LOADED = True
        elapsed = time.monotonic() - started
        logger.info(
            "Home screening model loaded in %.1fs. Classes: %s",
            elapsed, list(_id2label.values()),
        )


def is_home_model_loaded() -> bool:
    """Report whether the home model and processor are ready to serve."""
    return bool(HOME_MODEL_LOADED and _model is not None and _processor is not None)


def get_home_labels() -> list[str]:
    """List the human-readable class labels the home model can emit."""
    if not is_home_model_loaded():
        return []
    id2label = _id2label or getattr(getattr(_model, 'config', None), 'id2label', {})
    return list(id2label.values())


def predict_home(image_bytes: bytes) -> list[dict]:
    """Run home screening inference on raw image bytes.

    Pipeline::

        bytes → io.BytesIO → PIL.Image.open().convert('RGB')
              → AutoImageProcessor
              → torch.Tensor → model(tensor) inside torch.no_grad()
              → torch.softmax(logits, dim=-1)
              → list of {label, confidence} sorted by confidence descending

    **Never raises** on bad input — returns ``[]`` so the triage engine falls
    back to pixel-only cues.  This is critical: a corrupt photo must never
    block a screening where symptoms alone would have been enough.

    Args:
        image_bytes: Raw bytes of the uploaded smartphone photo.

    Returns:
        Predictions sorted by descending confidence, each
        ``{'label': str, 'confidence': float}``.  Empty list when the model
        is not loaded or the image is unreadable.
    """
    if not is_home_model_loaded():
        logger.debug("Home model not loaded — returning empty predictions.")
        return []

    if not image_bytes:
        return []

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except (
        Image.DecompressionBombError,
        Image.UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning(
            "Home model: could not open image, falling back to pixel cues: %s", exc
        )
        return []

    device = torch.device(Config.TORCH_DEVICE)
    try:
        with torch.no_grad():
            inputs = _processor(images=image, return_tensors='pt')
            if hasattr(inputs, 'to'):
                inputs = inputs.to(device)
            outputs = _model(**inputs)
            logits = outputs.logits if hasattr(outputs, 'logits') else outputs
    except Exception as exc:  # noqa: BLE001 — never crash on inference failure
        logger.error("Home model inference failed: %s", exc, exc_info=True)
        return []

    probs = torch.softmax(logits, dim=_LOGITS_AXIS)[0]
    id2label = getattr(getattr(_model, 'config', None), 'id2label', None) or _id2label

    return sorted(
        [
            {
                'label': id2label.get(i, id2label.get(str(i), f'Class {i}')),
                'confidence': round(probs[i].item() * 100, _CONFIDENCE_DECIMALS),
            }
            for i in range(len(probs))
        ],
        key=lambda item: item['confidence'],
        reverse=True,
    )
