"""
backend/model.py
────────────────
VisionAI inference engine supporting RETFound (ViT-Large/16) and HuggingFace AutoModels.

Single Responsibility
─────────────────────
Model lifecycle + the inference pipeline. Nothing else. This module knows nothing
about HTTP, Firestore, authentication or the Flask request cycle.

Hard constraints honoured (restructure spec §4.3):
  * MUST NOT import flask, firebase_admin, firestore or any HTTP library.
  * MUST NOT write to disk — every byte stays in volatile memory via io.BytesIO.
  * MUST wrap every forward pass in torch.no_grad().
  * MUST handle PIL.Image.DecompressionBombError (ZIP-bomb protection).
  * Model is loaded ONCE per WSGI worker at startup, never per request.
"""

import io
import logging
import os
import time
from types import SimpleNamespace

import numpy as np
import timm
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from transformers import AutoImageProcessor, AutoModelForImageClassification

from config import Config

logger = logging.getLogger('visionai.model')

# ── Module-level singletons (one set per WSGI worker process) ────────────────
_processor = None
_model = None
_id2label: dict[int, str] = {}

#: True once both the processor and the model are initialised.
MODEL_LOADED: bool = False

#: Percentage confidence values are rounded to this many decimal places.
_CONFIDENCE_DECIMALS = 2

#: Softmax is applied over the final logits axis.
_LOGITS_AXIS = -1

#: Standard RETFound inference transform (resize 224x224, ImageNet normalisation).
_RETFOUND_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class RETFoundClassifier(nn.Module):
    """RETFound ViT-Large backbone with multi-layer classification head."""

    def __init__(self, backbone: nn.Module, num_classes: int = 4, dropout: float = 0.3):
        super().__init__()
        self.backbone = backbone
        embed_dim = getattr(backbone, 'embed_dim', 1024)
        self.classifier = nn.Sequential(
            nn.LayerNorm(embed_dim),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, 512),
            nn.GELU(),
            nn.Dropout(dropout / 2),
            nn.Linear(512, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone.forward_features(x)
        cls_token = features[:, 0, :]
        return self.classifier(cls_token)


def _find_retfound_checkpoint(model_id: str) -> str | None:
    """Find a .pth checkpoint if model_id points to one or contains one."""
    if os.path.isfile(model_id) and model_id.endswith('.pth'):
        return model_id
    if os.path.isdir(model_id):
        candidate = os.path.join(model_id, 'retfound_classifier.pth')
        if os.path.isfile(candidate):
            return candidate
    return None


#: Fundus images always have a very dark circular border (vignetting from the fundus camera lens).
#: External eye photos have skin-tone pixels all the way to the edges — dark_border will be near 0.
_FUNDUS_DARK_BORDER_MIN = 0.30   # At least 30% of outer ring pixels must be near-black


def is_fundus_image(image_bytes: bytes) -> bool:
    """Heuristic check: does this image look like a retinal fundus photograph?

    The single most reliable discriminator is the **dark circular border**:
    fundus cameras produce a characteristic vignetting (circular black surround)
    because the image is cropped to the illuminated disc. External eye photos,
    selfies, or any non-fundus photo fill all the way to the edges with skin
    tones / background — they will not have this dark border.

    Secondary signals:
      - Balanced RGB (grayscale or near-grayscale with slight red tint) vs
        heavy red-channel dominance typical of skin tones.
      - Bright central region (illuminated retina) vs uniform background.

    This is a fast CPU-only check (~1 ms on a 224×224 image) that runs before
    the heavy ViT forward pass to reject obviously wrong image types.

    Args:
        image_bytes: Raw bytes of the uploaded image.

    Returns:
        True when the image passes the fundus dark-border criterion.
        False when the image clearly lacks the fundus dark-border vignetting,
        indicating it is probably not a retinal fundus photograph.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB').resize((128, 128))
    except Exception:  # noqa: BLE001
        return False  # If we can't even open it, let the main pipeline handle the error.

    arr = np.array(img, dtype=np.float32)  # shape: (128, 128, 3)
    h, w = arr.shape[:2]
    cx, cy = w // 2, h // 2

    y_idx, x_idx = np.ogrid[:h, :w]
    dist_from_centre = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)

    # ── PRIMARY: Dark border / vignetting (required for fundus) ──────────────
    # Outer ring = pixels at >80% of the inscribed radius.
    outer_ring_mask = dist_from_centre > (min(cx, cy) * 0.80)
    border_pixels = arr[outer_ring_mask]
    if border_pixels.size == 0:
        return False

    # Near-black = all channels < 30
    border_dark_fraction = float(np.mean(np.max(border_pixels, axis=1) < 30))
    has_dark_border = border_dark_fraction >= _FUNDUS_DARK_BORDER_MIN

    # ── SECONDARY: Skin-tone exclusion ───────────────────────────────────────
    # Exterior eye photos have extremely high red-channel dominance due to skin.
    # Real fundus photos have a redder tint than greens/blues, but not as extreme
    # as the 0.90+ seen in skin tones. Use this to reject obvious skin images.
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    red_dominant = float(np.mean((r > g) & (r > b)))
    is_skin_tone = red_dominant > 0.85  # Skin tones: ~0.90-0.98; fundus: ~0.3-0.65

    # ── TERTIARY: Grayscale OCT scan exclusion ───────────────────────────────
    # Cross-sectional OCT scans and monochrome vessel masks have R ≈ G ≈ B (channel diff < 3).
    # True color retinal fundus photography has rich chromatic contrast with red/orange dominance.
    channel_chroma = float(np.mean(np.abs(r - g) + np.abs(g - b)))
    is_grayscale_oct = channel_chroma < 4.0

    logger.debug(
        'Fundus heuristic: dark_border=%.3f(>=%s → %s) red_dom=%.3f(is_skin=%s) chroma=%.2f(is_oct=%s) → is_fundus=%s',
        border_dark_fraction, _FUNDUS_DARK_BORDER_MIN, has_dark_border,
        red_dominant, is_skin_tone,
        channel_chroma, is_grayscale_oct,
        has_dark_border and not is_skin_tone and not is_grayscale_oct,
    )

    # Must have a circular dark border, not look like skin, and not be a monochrome OCT scan.
    return has_dark_border and not is_skin_tone and not is_grayscale_oct


def crop_retina_circle(image: Image.Image, tol: int = 15) -> Image.Image:
    """Crop out the black camera frame to isolate the retina ROI.
    
    Ensures input image resolution matches the ROI cropping used during
    the 92.77% fine-tuning of the RETFound classifier.
    """
    img_np = np.array(image)
    if img_np.ndim != 3 or img_np.shape[2] < 3:
        return image
    gray = np.mean(img_np[:, :, :3], axis=2)
    mask = gray > tol
    if not np.any(mask):
        return image
    row_sum = np.sum(mask, axis=1)
    col_sum = np.sum(mask, axis=0)
    y_idx = np.where(row_sum > 0)[0]
    x_idx = np.where(col_sum > 0)[0]
    if len(y_idx) == 0 or len(x_idx) == 0:
        return image

    y_min, y_max = y_idx[0], y_idx[-1]
    x_min, x_max = x_idx[0], x_idx[-1]
    side = max(y_max - y_min, x_max - x_min)
    cy, cx = (y_min + y_max) // 2, (x_min + x_max) // 2

    y1 = max(0, cy - side // 2)
    y2 = min(img_np.shape[0], cy + side // 2)
    x1 = max(0, cx - side // 2)
    x2 = min(img_np.shape[1], cx + side // 2)
    return Image.fromarray(img_np[y1:y2, x1:x2])



def load_model() -> None:
    """Initialise the image processor and the classification model.

    Supports both:
      1. Local RETFound PyTorch checkpoints (``retfound_classifier.pth``) with
         ViT-Large backbone and custom classification head.
      2. HuggingFace Hub or local ``AutoModelForImageClassification`` models.

    Args:
        None.

    Returns:
        None.

    Raises:
        RuntimeError: If the weights cannot be loaded or initialised.
    """
    global _processor, _model, _id2label, MODEL_LOADED

    if MODEL_LOADED:
        logger.debug("load_model() called again — model already initialised.")
        return

    started = time.monotonic()
    device = torch.device(Config.TORCH_DEVICE)
    logger.info("Loading AI model: %s (device=%s)", Config.LOCAL_MODEL_ID, Config.TORCH_DEVICE)

    pth_path = _find_retfound_checkpoint(Config.LOCAL_MODEL_ID)

    try:
        if pth_path:
            logger.info("Loading RETFound ViT-Large PyTorch checkpoint: %s", pth_path)
            ckpt = torch.load(pth_path, map_location='cpu')
            num_classes = ckpt.get('num_classes', 4)

            backbone = timm.create_model(
                'vit_large_patch16_224',
                pretrained=False,
                num_classes=0,
                global_pool='',
            )
            ret_model = RETFoundClassifier(backbone, num_classes=num_classes)
            ret_model.load_state_dict(ckpt['model_state_dict'])
            ret_model.to(device)
            ret_model.eval()

            raw_id2label = ckpt.get('id2label') or {
                str(i): c for i, c in enumerate(ckpt.get('classes', []))
            }
            _id2label = {int(k): v for k, v in raw_id2label.items()}

            # Attach a mock config so inspection tools and tests see id2label
            ret_model.config = SimpleNamespace(id2label=_id2label)

            _model = ret_model
            _processor = _RETFOUND_TRANSFORM
        else:
            _processor = AutoImageProcessor.from_pretrained(Config.LOCAL_MODEL_ID)
            _model = AutoModelForImageClassification.from_pretrained(Config.LOCAL_MODEL_ID)
            _model.to(device)
            _model.eval()
            _id2label = {int(k): v for k, v in getattr(_model.config, 'id2label', {}).items()}

    except Exception as exc:  # noqa: BLE001 — re-raised as RuntimeError below
        _processor = _model = None
        _id2label = {}
        MODEL_LOADED = False
        logger.error("Failed to load AI model '%s': %s", Config.LOCAL_MODEL_ID, exc, exc_info=True)
        raise RuntimeError(f"AI model initialisation failed: {exc}") from exc

    MODEL_LOADED = True
    elapsed = time.monotonic() - started
    if elapsed > Config.MODEL_LOAD_TIMEOUT_SECONDS:
        logger.warning(
            "Model cold start took %.1fs, exceeding the %ds budget.",
            elapsed, Config.MODEL_LOAD_TIMEOUT_SECONDS,
        )
    logger.info(
        "AI model loaded in %.1fs. Classes: %s", elapsed, list(_id2label.values())
    )


def is_loaded() -> bool:
    """Report whether the model and processor are ready to serve inference."""
    return bool(MODEL_LOADED and _model is not None and _processor is not None)


def get_labels() -> list[str]:
    """List the human-readable class labels the loaded model can emit."""
    if not is_loaded():
        return []
    id2label = _id2label or getattr(getattr(_model, 'config', None), 'id2label', {})
    return list(id2label.values())


def predict(image_bytes: bytes) -> list[dict]:
    """Run inference on raw image bytes.

    Pipeline:
        bytes -> io.BytesIO -> PIL.Image.open().convert('RGB')
              -> Image Processor / Normalisation
              -> torch.Tensor -> model(tensor) inside torch.no_grad()
              -> torch.softmax(logits, dim=-1)
              -> list of {label, confidence, low_confidence?} sorted by confidence descending

    No bytes ever touch the filesystem.

    Args:
        image_bytes: Raw bytes of a candidate image file.

    Returns:
        Predictions sorted by descending confidence. The first element includes
        a ``low_confidence`` boolean flag that is True when the top prediction
        is below 30%, indicating the image may not be a valid fundus photograph.
    """
    if not is_loaded():
        raise RuntimeError("AI model is not loaded")

    try:
        image_stream = io.BytesIO(image_bytes)
        image = Image.open(image_stream).convert('RGB')
        image = crop_retina_circle(image)
    except Image.DecompressionBombError as exc:
        raise ValueError(f"Image exceeds safe decompression limits: {exc}") from exc
    except (Image.UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"Invalid or corrupted image data: {exc}") from exc

    device = torch.device(Config.TORCH_DEVICE)
    with torch.no_grad():
        if isinstance(_processor, transforms.Compose):
            tensor = _processor(image).unsqueeze(0).to(device)
            outputs = _model(tensor)
            logits = outputs.logits if hasattr(outputs, 'logits') else outputs
        else:
            inputs = _processor(images=image, return_tensors='pt')
            if hasattr(inputs, 'to'):
                inputs = inputs.to(device)
            outputs = _model(**inputs)
            logits = outputs.logits if hasattr(outputs, 'logits') else outputs

    probs = torch.softmax(logits, dim=_LOGITS_AXIS)[0]
    id2label = getattr(getattr(_model, 'config', None), 'id2label', None) or _id2label

    sorted_predictions = sorted(
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

    # Fix D: Tag the result set with a low_confidence flag when the model is not
    # confident enough — typically caused by an out-of-distribution input image
    # (e.g., an external eye photo instead of a retinal fundus photograph).
    _INCONCLUSIVE_THRESHOLD = 30.0
    if sorted_predictions and sorted_predictions[0]['confidence'] < _INCONCLUSIVE_THRESHOLD:
        sorted_predictions[0]['low_confidence'] = True
        sorted_predictions[0]['inconclusive_reason'] = (
            f"Top class confidence ({sorted_predictions[0]['confidence']}%) is below the "
            f"{_INCONCLUSIVE_THRESHOLD}% reliability threshold. The image may not be a "
            "retinal fundus photograph."
        )

    return sorted_predictions
