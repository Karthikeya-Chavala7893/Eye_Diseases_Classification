"""
tests/test_predict.py
─────────────────────
Integration tests for the AI inference route:
  - POST /predict

The HuggingFace model and processor are mocked in conftest.py.
No actual image processing or GPU/CPU inference occurs during these tests.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
import torch


# ═════════════════════════════════════════════════════════════════════════════
# UNAUTHENTICATED ACCESS
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictUnauthenticated:
    """Verify /predict is protected by login_required."""

    def test_unauthenticated_request_returns_401(self, client, minimal_png):
        """/predict without a session returns 401 (JSON, not redirect)."""
        data = {'image': (io.BytesIO(minimal_png), 'retina.png', 'image/png')}
        res = client.post('/predict',
                          data=data,
                          content_type='multipart/form-data',
                          headers={'Accept': 'application/json'})

        assert res.status_code == 401
        body = res.get_json()
        assert body['success'] is False

    def test_unauthenticated_no_file_returns_401(self, client):
        """/predict without any payload and no session returns 401."""
        res = client.post('/predict',
                          content_type='multipart/form-data',
                          headers={'Accept': 'application/json'})
        assert res.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# AUTHENTICATED — INPUT VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictValidation:
    """Verify input validation on /predict with an authenticated session."""

    def test_no_image_field_returns_400(self, authenticated_client):
        """POST without an 'image' field in form data returns HTTP 400."""
        res = authenticated_client.post('/predict',
                                        data={},
                                        content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False

    def test_empty_filename_returns_400(self, authenticated_client):
        """Uploading a file with no filename returns HTTP 400."""
        data = {'image': (io.BytesIO(b'data'), '', 'image/png')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False

    def test_invalid_extension_txt_returns_400(self, authenticated_client):
        """A .txt file is rejected with HTTP 400 — extension not in ALLOWED_EXTENSIONS."""
        data = {'image': (io.BytesIO(b'not an image'), 'notes.txt', 'text/plain')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False

    def test_invalid_extension_exe_returns_400(self, authenticated_client):
        """A .exe file is rejected with HTTP 400."""
        data = {'image': (io.BytesIO(b'MZ\x90\x00'), 'malware.exe', 'application/octet-stream')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False

    def test_invalid_extension_pdf_returns_400(self, authenticated_client):
        """A .pdf file is rejected with HTTP 400."""
        data = {'image': (io.BytesIO(b'%PDF-1.4'), 'report.pdf', 'application/pdf')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False


# ═════════════════════════════════════════════════════════════════════════════
# AUTHENTICATED — SUCCESSFUL INFERENCE
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictInference:
    """Verify successful inference with mocked model."""

    def test_valid_png_returns_200_with_predictions(self, authenticated_client, minimal_png):
        """Valid PNG upload returns HTTP 200 with a non-empty predictions list."""
        import app as flask_app

        # Ensure model globals report as loaded
        flask_app.MODEL_LOADED = True

        # Mock processor to return a proper tensor dict
        flask_app.image_processor = MagicMock(
            return_value={'pixel_values': torch.zeros(1, 3, 224, 224)}
        )
        # Mock model to return logits
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[5.0, 1.0, 0.5]])
        flask_app.eye_model = MagicMock(return_value=mock_output)
        flask_app.eye_model.config.id2label = {0: 'Healthy_Retina', 1: 'Glaucoma', 2: 'Cataract'}
        flask_app.eye_model.eval = MagicMock()

        data = {'image': (io.BytesIO(minimal_png), 'retina.png', 'image/png')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')

        assert res.status_code == 200
        body = res.get_json()
        assert body['success'] is True
        assert isinstance(body['predictions'], list)
        assert len(body['predictions']) > 0

    def test_predictions_are_sorted_by_confidence(self, authenticated_client, minimal_png):
        """Predictions list must be sorted descending by confidence score."""
        import app as flask_app

        flask_app.MODEL_LOADED = True
        flask_app.image_processor = MagicMock(
            return_value={'pixel_values': torch.zeros(1, 3, 224, 224)}
        )
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[1.0, 5.0, 3.0]])
        flask_app.eye_model = MagicMock(return_value=mock_output)
        flask_app.eye_model.config.id2label = {0: 'Healthy_Retina', 1: 'Glaucoma', 2: 'Cataract'}
        flask_app.eye_model.eval = MagicMock()

        data = {'image': (io.BytesIO(minimal_png), 'scan.png', 'image/png')}
        res = authenticated_client.post('/predict',
                                        data=data,
                                        content_type='multipart/form-data')

        assert res.status_code == 200
        preds = res.get_json()['predictions']
        confidences = [p['confidence'] for p in preds]
        assert confidences == sorted(confidences, reverse=True), \
            "Predictions are not sorted by descending confidence"

    def test_model_not_loaded_returns_503(self, authenticated_client, minimal_png):
        """If MODEL_LOADED is False, the route returns HTTP 503 Service Unavailable."""
        import app as flask_app

        original = flask_app.MODEL_LOADED
        flask_app.MODEL_LOADED = False
        try:
            data = {'image': (io.BytesIO(minimal_png), 'retina.png', 'image/png')}
            res = authenticated_client.post('/predict',
                                            data=data,
                                            content_type='multipart/form-data')
            assert res.status_code == 503
            body = res.get_json()
            assert body['success'] is False
        finally:
            flask_app.MODEL_LOADED = original  # restore for subsequent tests


# ═════════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Verify OWASP security headers are injected on every response (P-17)."""

    def test_x_frame_options_deny(self, client):
        """All responses carry X-Frame-Options: DENY."""
        res = client.get('/login')
        assert res.headers.get('X-Frame-Options') == 'DENY'

    def test_x_content_type_options_nosniff(self, client):
        """All responses carry X-Content-Type-Options: nosniff."""
        res = client.get('/login')
        assert res.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_csp_header_present(self, client):
        """Content-Security-Policy header is present on every response."""
        res = client.get('/login')
        assert 'Content-Security-Policy' in res.headers
        assert "default-src 'self'" in res.headers['Content-Security-Policy']
