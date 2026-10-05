"""
backend/tests/test_predict.py
─────────────────────────────
Integration tests for POST /api/predict, GET /api/health, GET /api/config and
the global security-header middleware.

Everything is mocked (Firestore, Firebase JWT verification, HuggingFace model),
so the suite performs zero network I/O and zero disk writes.
"""

import io

import pytest

import app as flask_app
import model as model_module

PREDICT_URL = '/api/predict'


def _upload(payload: bytes, filename: str, mimetype: str = 'image/png') -> dict:
    """Build a multipart form dict for the Flask test client."""
    return {'image': (io.BytesIO(payload), filename, mimetype)}


# ═════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION GATE
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictAuthentication:
    """/api/predict must reject every unauthenticated caller."""

    def test_predict_missing_auth_header_returns_401(self, client, minimal_png):
        res = client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                          content_type='multipart/form-data')
        assert res.status_code == 401
        body = res.get_json()
        assert body['success'] is False
        assert body['error'] == 'Missing Authorization header'

    def test_predict_malformed_auth_header_returns_401(self, client, minimal_png):
        res = client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                          content_type='multipart/form-data',
                          headers={'Authorization': 'Token abc123'})
        assert res.status_code == 401
        assert res.get_json()['error'] == 'Invalid token format'

    def test_predict_expired_token_returns_401_token_expired(
        self, client, mock_verify_token, auth_headers, minimal_png
    ):
        from firebase_admin import auth as fb_auth
        mock_verify_token.side_effect = fb_auth.ExpiredIdTokenError('expired', cause=None)

        res = client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                          content_type='multipart/form-data', headers=auth_headers)
        assert res.status_code == 401
        assert res.get_json()['error'] == 'Token expired'

    def test_predict_revoked_token_returns_401_token_revoked(
        self, client, mock_verify_token, auth_headers, minimal_png
    ):
        from firebase_admin import auth as fb_auth
        mock_verify_token.side_effect = fb_auth.RevokedIdTokenError('revoked')

        res = client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                          content_type='multipart/form-data', headers=auth_headers)
        assert res.status_code == 401
        assert res.get_json()['error'] == 'Token revoked'

    def test_predict_invalid_token_returns_401_invalid_token(
        self, client, mock_verify_token, auth_headers, minimal_png
    ):
        from firebase_admin import auth as fb_auth
        mock_verify_token.side_effect = fb_auth.InvalidIdTokenError('bad signature')

        res = client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                          content_type='multipart/form-data', headers=auth_headers)
        assert res.status_code == 401
        assert res.get_json()['error'] == 'Invalid token'


# ═════════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictValidation:
    """Server-side upload validation, independent of any client-side check."""

    def test_predict_missing_image_field_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL, data={}, content_type='multipart/form-data')
        assert res.status_code == 400
        body = res.get_json()
        assert body['success'] is False
        assert body['error'] == 'No image uploaded'

    def test_predict_empty_filename_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL, data=_upload(b'data', ''),
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert res.get_json()['success'] is False

    @pytest.mark.parametrize('filename,mimetype', [
        ('notes.txt', 'text/plain'),
        ('malware.exe', 'application/octet-stream'),
        ('report.pdf', 'application/pdf'),
        ('archive.zip', 'application/zip'),
    ])
    def test_predict_disallowed_extension_returns_400(self, authed_client, filename, mimetype):
        res = authed_client.post(PREDICT_URL, data=_upload(b'payload', filename, mimetype),
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert 'Invalid format' in res.get_json()['error']

    def test_predict_mismatched_mime_type_returns_400(self, authed_client, minimal_png):
        """A .png name with a non-image content type is rejected (defence in depth)."""
        res = authed_client.post(
            PREDICT_URL,
            data=_upload(minimal_png, 'retina.png', 'application/octet-stream'),
            content_type='multipart/form-data',
        )
        assert res.status_code == 400
        assert res.get_json()['error'] == 'Invalid image content type'

    def test_predict_corrupted_image_bytes_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL, data=_upload(b'not-a-real-png', 'retina.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert res.get_json()['success'] is False

    def test_predict_oversized_payload_returns_413(self, authed_client):
        """A body larger than MAX_CONTENT_LENGTH is rejected with RFC 7807 details."""
        oversized = b'\x00' * (flask_app.Config.MAX_CONTENT_LENGTH + 1024)
        res = authed_client.post(PREDICT_URL, data=_upload(oversized, 'huge.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 413
        body = res.get_json()
        assert body['success'] is False
        assert body['status'] == 413
        assert body['title'] == 'Payload Too Large'


# ═════════════════════════════════════════════════════════════════════════════
# SUCCESSFUL INFERENCE
# ═════════════════════════════════════════════════════════════════════════════

class TestPredictInference:
    """Happy path and model-availability behaviour."""

    def test_predict_valid_png_returns_200_with_predictions(self, authed_client, minimal_png):
        res = authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 200
        body = res.get_json()
        assert body['success'] is True

        data = body['data']
        assert data['model'] == flask_app.Config.LOCAL_MODEL_ID
        assert data['inference'] == 'local'
        assert data['user'] == 'Test User'
        assert len(data['predictions']) == 3
        assert set(data['predictions'][0]) == {'label', 'confidence'}

    def test_predict_results_are_sorted_by_confidence_descending(self, authed_client, minimal_png):
        res = authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'scan.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 200
        confidences = [p['confidence'] for p in res.get_json()['data']['predictions']]
        assert confidences == sorted(confidences, reverse=True)

    def test_predict_persists_scan_without_storing_image(self, authed_client, mock_db, minimal_png):
        """A successful prediction writes a scan document containing only a hash."""
        res = authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 200

        mock_db.collection.return_value.add.assert_called_once()
        document = mock_db.collection.return_value.add.call_args[0][0]
        assert len(document['imageHash']) == 64          # SHA-256 hex digest
        assert 'image' not in document
        assert not any(isinstance(v, bytes) for v in document.values())

    def test_predict_survives_firestore_write_failure(self, authed_client, mock_db, minimal_png):
        """Scan persistence is best-effort — a Firestore outage must not fail screening."""
        mock_db.collection.return_value.add.side_effect = Exception('firestore down')

        res = authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                                 content_type='multipart/form-data')
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_predict_model_not_loaded_returns_503(self, authed_client, minimal_png):
        original = model_module.MODEL_LOADED
        model_module.MODEL_LOADED = False
        try:
            res = authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                                     content_type='multipart/form-data')
            assert res.status_code == 503
            body = res.get_json()
            assert body['success'] is False
            assert body['error'] == 'AI model unavailable'
        finally:
            model_module.MODEL_LOADED = original


# ═════════════════════════════════════════════════════════════════════════════
# RATE LIMITING
# ═════════════════════════════════════════════════════════════════════════════

class TestRateLimiting:
    """Flask-Limiter guards the expensive inference endpoint."""

    def test_predict_exceeding_rate_limit_returns_429(self, authed_client, minimal_png):
        flask_app.limiter.reset()
        flask_app.limiter.enabled = True
        try:
            statuses = [
                authed_client.post(PREDICT_URL, data=_upload(minimal_png, 'retina.png'),
                                   content_type='multipart/form-data').status_code
                for _ in range(12)
            ]
        finally:
            flask_app.limiter.enabled = False
            flask_app.limiter.reset()

        assert 429 in statuses, f'Expected a 429 within 12 requests, got {statuses}'
        assert statuses[0] == 200

    def test_health_endpoint_is_exempt_from_rate_limits(self, client):
        flask_app.limiter.reset()
        flask_app.limiter.enabled = True
        try:
            statuses = [client.get('/api/health').status_code for _ in range(60)]
        finally:
            flask_app.limiter.enabled = False
            flask_app.limiter.reset()

        assert set(statuses) == {200}


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPublicEndpoints:
    """/api/health and /api/config require no authentication."""

    def test_health_returns_subsystem_status(self, client, mock_db, mock_model):
        res = client.get('/api/health')
        assert res.status_code == 200
        data = res.get_json()['data']
        assert data['model_loaded'] is True
        assert data['firebase_connected'] is True
        assert data['status'] == 'healthy'

    def test_config_returns_upload_limits(self, client):
        res = client.get('/api/config')
        assert res.status_code == 200
        data = res.get_json()['data']
        assert data['maxFileSizeBytes'] == 16 * 1024 * 1024
        assert 'image/png' in data['allowedMimeTypes']
        assert 'png' in data['allowedExtensions']

    def test_unknown_route_returns_json_404(self, client):
        res = client.get('/api/does-not-exist')
        assert res.status_code == 404
        assert res.get_json()['success'] is False


# ═════════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """OWASP headers are injected on every response, success or failure."""

    @pytest.mark.parametrize('path', ['/api/health', '/api/config', '/api/does-not-exist'])
    def test_security_headers_present_on_every_response(self, client, path):
        res = client.get(path)
        assert res.headers['X-Frame-Options'] == 'DENY'
        assert res.headers['X-Content-Type-Options'] == 'nosniff'
        assert res.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        assert "default-src 'none'" in res.headers['Content-Security-Policy']

    def test_cors_allows_whitelisted_origin(self, client):
        res = client.get('/api/health', headers={'Origin': 'http://localhost:3000'})
        assert res.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'

    def test_cors_rejects_unlisted_origin(self, client):
        res = client.get('/api/health', headers={'Origin': 'http://evil.com'})
        assert res.headers.get('Access-Control-Allow-Origin') is None
