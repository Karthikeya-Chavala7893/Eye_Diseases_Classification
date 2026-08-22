"""
tests/conftest.py
─────────────────
Shared pytest fixtures for the VisionAI test suite.

Strategy
────────
app.py has two module-level side-effects that must be neutralised before import:
  1. `create_client(...)` — calls Supabase with real credentials.
  2. `AutoImageProcessor / AutoModelForImageClassification.from_pretrained(...)` — downloads
     ~500MB of HuggingFace weights.

Both are patched via `unittest.mock.patch` before `app` is imported, so the test
process never touches the internet and runs in < 5 seconds.
"""

import io
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure the project root is on the path so `import app` works ──────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Minimal environment so validate_config() doesn't raise RuntimeError ───────
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest-only')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'test-supabase-key')
os.environ.setdefault('GOOGLE_CLIENT_ID', '')
os.environ.setdefault('GOOGLE_CLIENT_SECRET', '')


def _make_mock_supabase():
    """Return a MagicMock that mimics the Supabase client's fluent query API."""
    mock_sb = MagicMock()
    # Default: table().select().eq().execute() → no data (user not found)
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # Default: table().insert().execute() → successful insert
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{'id': 'mock-id'}])
    return mock_sb


def _make_mock_model():
    """Return a MagicMock that mimics a HuggingFace image classification model."""
    mock_model = MagicMock()
    mock_model.eval.return_value = mock_model
    mock_model.config.id2label = {0: 'Healthy_Retina', 1: 'Glaucoma', 2: 'Cataract'}

    import torch
    # Simulate logits: highest score for class 0 (Healthy_Retina)
    mock_logits = torch.tensor([[5.0, 1.0, 0.5]])
    mock_output = MagicMock()
    mock_output.logits = mock_logits
    mock_model.return_value = mock_output
    return mock_model


def _make_mock_processor():
    """Return a MagicMock that mimics AutoImageProcessor."""
    mock_proc = MagicMock()
    import torch
    mock_proc.return_value = {'pixel_values': torch.zeros(1, 3, 224, 224)}
    return mock_proc


# ── Patch supabase and HuggingFace before app is imported ─────────────────────
_mock_supabase_instance = _make_mock_supabase()
_mock_model_instance = _make_mock_model()
_mock_processor_instance = _make_mock_processor()

with patch('supabase.create_client', return_value=_mock_supabase_instance), \
     patch('transformers.AutoImageProcessor.from_pretrained', return_value=_mock_processor_instance), \
     patch('transformers.AutoModelForImageClassification.from_pretrained', return_value=_mock_model_instance):
    import app as flask_app  # noqa: E402 — intentional deferred import


# ── Inject mocks into the already-imported app module globals ─────────────────
flask_app.supabase = _mock_supabase_instance
flask_app.image_processor = _mock_processor_instance
flask_app.eye_model = _mock_model_instance
flask_app.MODEL_LOADED = True


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def application():
    """Configured Flask application for the full test session."""
    flask_app.app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,   # Disable CSRF so test POSTs don't need tokens
        'LOGIN_DISABLED': False,
        'SERVER_NAME': 'localhost',
    })
    # Bypass Flask-Limiter for the entire test session by replacing the internal
    # rate-check method with a no-op. This is the only reliable way to disable
    # the limiter after init_app() has already been called.
    with patch.object(flask_app.limiter, '_check_request_limit'):
        yield flask_app.app


@pytest.fixture
def client(application):
    """Fresh test client per test — session state is isolated."""
    with application.test_client() as c:
        with application.app_context():
            yield c


@pytest.fixture
def mock_supabase():
    """Expose the shared Supabase mock for per-test configuration."""
    return _mock_supabase_instance


@pytest.fixture
def registered_user(client, mock_supabase):
    """
    Helper fixture: registers a test user and returns their credentials.
    Resets the supabase mock so:
      - get_user_by_email returns empty (no duplicate) during registration
      - insert returns success
      - get_user_by_email returns the user during login
    """
    from werkzeug.security import generate_password_hash

    email = 'test@visionai.com'
    password = 'SecurePass123'
    user_id = 'test-uuid-1234'

    stored_user = {
        'id': user_id,
        'email': email,
        'name': 'Test User',
        'phone': None,
        'password_hash': generate_password_hash(password),
        'login_method': 'Password',
        'role': 'user',
        'is_active': True,
        'last_login': None,
        'created_at': '2026-01-01 00:00:00',
    }

    # During registration: no existing user → empty select result
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[stored_user])

    res = client.post('/auth/register',
                      json={'email': email, 'password': password, 'name': 'Test User'},
                      content_type='application/json')
    assert res.status_code == 200, f"Setup fixture registration failed: {res.get_data(as_text=True)}"

    # After registration: select now returns the stored user (for login)
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[stored_user])

    return {'email': email, 'password': password, 'user_id': user_id, 'data': stored_user}


@pytest.fixture
def authenticated_client(client, registered_user, mock_supabase):
    """Test client with an active authenticated session."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
        MagicMock(data=[registered_user['data']])

    res = client.post('/auth/login',
                      json={'email': registered_user['email'], 'password': registered_user['password']},
                      content_type='application/json')
    assert res.status_code == 200, f"Login in fixture failed: {res.get_data(as_text=True)}"
    return client


@pytest.fixture
def minimal_png():
    """Returns a 1×1 pixel valid PNG as bytes (no disk I/O)."""
    import zlib
    import struct

    def png_chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    png = (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
        + png_chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
        + png_chunk(b'IEND', b'')
    )
    return png
