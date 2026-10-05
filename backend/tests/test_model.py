"""
backend/tests/test_model.py
───────────────────────────
Unit tests for the inference engine (``backend/model.py``).

The HuggingFace processor and network are MagicMocks with deterministic logits,
so no weights are downloaded and no tensors of consequence are computed.
"""

import io
import struct
import zlib
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

import model as model_module
from config import Config
from tests.static_analysis import (
    called_function_names,
    imported_modules,
    source_without_comments_or_docstrings,
)


def _png(width: int = 1, height: int = 1) -> bytes:
    """Generate a valid PNG of the requested size entirely in memory."""
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), (10, 20, 30)).save(buffer, format='PNG')
    return buffer.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# MODULE CONTRACT
# ═════════════════════════════════════════════════════════════════════════════

class TestModuleIsolation:
    """model.py must stay free of web, database and filesystem concerns."""

    FORBIDDEN_IMPORTS = {
        'flask', 'firebase_admin', 'firestore', 'google', 'requests',
        'httpx', 'urllib', 'db', 'auth', 'tempfile', 'pathlib', 'shutil',
    }

    def test_model_module_does_not_import_flask_or_firebase(self):
        leaked = imported_modules(model_module.__file__) & self.FORBIDDEN_IMPORTS
        assert not leaked, f'model.py imports forbidden modules: {sorted(leaked)}'

    def test_model_module_never_writes_to_disk(self):
        """Only PIL's in-memory Image.open is allowed; no file writes anywhere."""
        calls = called_function_names(model_module.__file__)
        for forbidden in ('save', 'write', 'write_bytes', 'write_text',
                          'NamedTemporaryFile', 'mkstemp'):
            assert forbidden not in calls, f'model.py must not call {forbidden}()'

        code = source_without_comments_or_docstrings(model_module.__file__)
        assert 'BytesIO' in code, 'inference must stream through io.BytesIO'

    def test_inference_runs_under_no_grad(self):
        code = source_without_comments_or_docstrings(model_module.__file__)
        assert 'with torch.no_grad():' in code


# ═════════════════════════════════════════════════════════════════════════════
# LIFECYCLE
# ═════════════════════════════════════════════════════════════════════════════

class TestModelLifecycle:
    """load_model() is idempotent, fail-fast and reflected by is_loaded()."""

    def test_is_loaded_true_after_successful_load(self, mock_model):
        assert model_module.is_loaded() is True

    def test_get_labels_returns_model_classes(self, mock_model):
        assert model_module.get_labels() == ['Healthy_Retina', 'Glaucoma', 'Cataract']

    def test_load_model_is_idempotent(self, mock_model):
        with patch('model.AutoImageProcessor.from_pretrained') as processor_loader:
            model_module.load_model()
        processor_loader.assert_not_called()

    def test_load_model_failure_raises_runtime_error_and_clears_state(self, monkeypatch):
        monkeypatch.setattr(model_module, 'MODEL_LOADED', False)
        monkeypatch.setattr(model_module, '_processor', None)
        monkeypatch.setattr(model_module, '_model', None)

        with patch('model.AutoImageProcessor.from_pretrained',
                   side_effect=OSError('network unreachable')):
            with pytest.raises(RuntimeError, match='AI model initialisation failed'):
                model_module.load_model()

        assert model_module.is_loaded() is False

    def test_predict_without_loaded_model_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr(model_module, 'MODEL_LOADED', False)
        with pytest.raises(RuntimeError, match='not loaded'):
            model_module.predict(_png())


# ═════════════════════════════════════════════════════════════════════════════
# INFERENCE PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

class TestPredict:
    """The prediction contract: sorted, rounded, complete and label-mapped."""

    def test_predict_returns_one_entry_per_class(self, mock_model):
        results = model_module.predict(_png())
        assert len(results) == len(mock_model.config.id2label)
        assert {r['label'] for r in results} == set(mock_model.config.id2label.values())

    def test_predict_sorts_by_confidence_descending(self, mock_model):
        output = MagicMock()
        output.logits = torch.tensor([[1.0, 5.0, 3.0]])
        mock_model.return_value = output

        results = model_module.predict(_png())
        assert [r['label'] for r in results] == ['Glaucoma', 'Cataract', 'Healthy_Retina']
        confidences = [r['confidence'] for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_predict_confidences_are_percentages_summing_to_100(self, mock_model):
        output = MagicMock()
        output.logits = torch.tensor([[2.0, 1.0, 0.5]])
        mock_model.return_value = output

        results = model_module.predict(_png())
        assert sum(r['confidence'] for r in results) == pytest.approx(100.0, abs=0.05)

    def test_predict_rounds_confidence_to_two_decimals(self, mock_model):
        for result in model_module.predict(_png()):
            assert round(result['confidence'], 2) == result['confidence']

    def test_predict_accepts_larger_images(self, mock_model):
        assert model_module.predict(_png(64, 64))

    def test_predict_converts_input_to_rgb(self, mock_model):
        """Greyscale and palette images are normalised before processing."""
        buffer = io.BytesIO()
        Image.new('L', (8, 8), 128).save(buffer, format='PNG')
        assert model_module.predict(buffer.getvalue())

    @pytest.mark.parametrize('payload', [
        b'',
        b'not-an-image-at-all',
        b'%PDF-1.4 fake pdf',
        b'\x89PNG\r\n\x1a\n' + b'\x00' * 32,   # truncated PNG header
    ])
    def test_predict_invalid_payload_raises_value_error(self, mock_model, payload):
        with pytest.raises(ValueError):
            model_module.predict(payload)

    def test_predict_decompression_bomb_raises_value_error(self, mock_model):
        with patch('model.Image.open', side_effect=Image.DecompressionBombError('too big')):
            with pytest.raises(ValueError, match='decompression'):
                model_module.predict(_png())

    def test_predict_uses_the_configured_model_id(self):
        # Verify the model ID is set to the ensemble classifier (not the old baselines).
        # Accepts either the HuggingFace repo ID or a local path pointing to the cached weights.
        model_id = Config.LOCAL_MODEL_ID
        assert model_id, "LOCAL_MODEL_ID must not be empty"
        assert 'NeuronZero' not in model_id, (
            "Model ID still points to the old EfficientNetB0 baseline — "
            "update LOCAL_MODEL_ID to the ensemble classifier."
        )
        # Confirm it references the ensemble fine-tuned checkpoint
        assert 'ensemble' in model_id.lower() or 'Karthikeya' in model_id, (
            f"Expected an ensemble checkpoint, got: {model_id}"
        )
