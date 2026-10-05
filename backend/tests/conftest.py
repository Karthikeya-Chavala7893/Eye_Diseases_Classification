"""
backend/tests/conftest.py
─────────────────────────
Shared pytest fixtures for the VisionAI backend suite.

Offline guarantee (constraint #31)
──────────────────────────────────
Importing ``app`` triggers two side effects that would otherwise hit the network:

  1. ``db.init_firestore()``  -> ``firebase_admin.initialize_app`` + ``firestore.client``
  2. ``model.load_model()``   -> downloads ~20MB of HuggingFace weights

Both are patched before the import below, so the whole suite runs in seconds
with zero sockets opened. ``firebase_admin.auth.verify_id_token`` is patched per
test through the ``mock_verify_token`` fixture.
"""

import os
import struct
import sys
import zlib
from unittest.mock import MagicMock, patch

import pytest
import torch

# ── Make backend/ importable regardless of the pytest invocation directory ────
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# ── Deterministic test environment (overrides anything in backend/.env) ───────
os.environ['SECRET_KEY'] = 'test-secret-key-for-pytest-only-32chars'
os.environ['FLASK_ENV'] = 'development'
os.environ['FIREBASE_CREDENTIALS_PATH'] = 'firebase-credentials.json'
os.environ['FIREBASE_STORAGE_BUCKET'] = 'test-bucket.appspot.com'
os.environ['ALLOWED_ORIGINS'] = 'http://localhost:3000'
os.environ['CHECK_TOKEN_REVOKED'] = 'false'
os.environ['LOCAL_MODEL_ID'] = 'mock-ensemble-model'

#: Class labels the mocked classifier reports.
MOCK_LABELS = {0: 'Healthy_Retina', 1: 'Glaucoma', 2: 'Cataract'}

#: Claims returned by the patched verify_id_token for an authenticated caller.
TEST_CLAIMS = {
    'uid': 'test-uid-1234',
    'email': 'test@visionai.com',
    'name': 'Test User',
    'firebase': {'sign_in_provider': 'password'},
}


# ═════════════════════════════════════════════════════════════════════════════
# MOCK BUILDERS
# ═════════════════════════════════════════════════════════════════════════════

def _make_mock_firestore() -> MagicMock:
    """Build a MagicMock mimicking the Firestore fluent client API."""
    client = MagicMock(name='firestore_client')

    # collection().document().get() -> missing document by default
    missing_doc = MagicMock()
    missing_doc.exists = False
    missing_doc.to_dict.return_value = None
    client.collection.return_value.document.return_value.get.return_value = missing_doc
    client.collection.return_value.document.return_value.set.return_value = None

    # collection().add() -> (write_result, doc_ref)
    added_ref = MagicMock()
    added_ref.id = 'scan-doc-id'
    client.collection.return_value.add.return_value = (MagicMock(), added_ref)

    # collection().where().order_by().limit().get() -> no history by default
    (client.collection.return_value
        .where.return_value
        .order_by.return_value
        .limit.return_value
        .get.return_value) = []

    return client


def _make_mock_model(logits: list[float] | None = None) -> MagicMock:
    """Build a MagicMock mimicking a HuggingFace image-classification model."""
    mock = MagicMock(name='eye_model')
    mock.eval.return_value = mock
    mock.to.return_value = mock
    mock.config.id2label = dict(MOCK_LABELS)

    output = MagicMock()
    output.logits = torch.tensor([logits or [5.0, 1.0, 0.5]])
    mock.return_value = output
    return mock


def _make_mock_processor() -> MagicMock:
    """Build a MagicMock mimicking AutoImageProcessor."""
    mock = MagicMock(name='image_processor')
    mock.return_value = {'pixel_values': torch.zeros(1, 3, 224, 224)}
    return mock


# ═════════════════════════════════════════════════════════════════════════════
# PATCHED IMPORT OF THE APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

_mock_firestore = _make_mock_firestore()
_mock_model = _make_mock_model()
_mock_processor = _make_mock_processor()

with patch('firebase_admin.initialize_app', return_value=None), \
     patch('firebase_admin.credentials.Certificate',
           return_value=MagicMock(project_id='test-project')), \
     patch('firebase_admin.firestore.client', return_value=_mock_firestore), \
     patch('transformers.AutoImageProcessor.from_pretrained', return_value=_mock_processor), \
     patch('transformers.AutoModelForImageClassification.from_pretrained',
           return_value=_mock_model):
    import app as flask_app        # noqa: E402 — intentional deferred import
    import db as db_module         # noqa: E402
    import model as model_module   # noqa: E402


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def application():
    """Configured Flask application for the whole test session."""
    flask_app.app.config.update({'TESTING': True, 'SERVER_NAME': 'localhost'})
    # Limits are off by default so unrelated tests never trip them. The
    # dedicated rate-limit test re-enables the limiter around its own requests.
    flask_app.limiter.enabled = False
    yield flask_app.app
    flask_app.limiter.enabled = True


@pytest.fixture
def client(application):
    """Fresh unauthenticated test client per test."""
    with application.test_client() as test_client:
        with application.app_context():
            yield test_client


@pytest.fixture
def mock_db():
    """The shared Firestore mock, reset to its default behaviour per test.

    ``return_value=True, side_effect=True`` matters: without them a test that
    installs a failure (``add.side_effect = Exception(...)``) would leak that
    failure into every later test sharing this mock.
    """
    _mock_firestore.reset_mock(return_value=True, side_effect=True)

    missing_doc = MagicMock()
    missing_doc.exists = False
    missing_doc.to_dict.return_value = None
    _mock_firestore.collection.return_value.document.return_value.get.return_value = missing_doc
    _mock_firestore.collection.return_value.document.return_value.set.return_value = None

    added_ref = MagicMock()
    added_ref.id = 'scan-doc-id'
    _mock_firestore.collection.return_value.add.return_value = (MagicMock(), added_ref)

    (_mock_firestore.collection.return_value
        .where.return_value
        .order_by.return_value
        .limit.return_value
        .get.return_value) = []

    db_module._client = _mock_firestore
    return _mock_firestore


@pytest.fixture
def mock_model():
    """Ensure model.py reports a loaded, deterministic classifier."""
    model_module._processor = _mock_processor
    model_module._model = _mock_model
    model_module._id2label = dict(MOCK_LABELS)
    model_module.MODEL_LOADED = True
    yield _mock_model
    model_module.MODEL_LOADED = True


@pytest.fixture
def mock_verify_token():
    """Patch Firebase JWT verification so any Bearer token resolves to TEST_CLAIMS.

    Yields the patched function so individual tests can override ``side_effect``
    to simulate expired, revoked or malformed tokens.
    """
    with patch('firebase_admin.auth.verify_id_token', return_value=dict(TEST_CLAIMS)) as mocked:
        yield mocked


@pytest.fixture
def auth_headers():
    """Authorization header carrying a syntactically valid Bearer token."""
    return {'Authorization': 'Bearer valid.test.token'}


@pytest.fixture
def authed_client(client, mock_verify_token, mock_db, mock_model):
    """Test client whose requests carry a verified Bearer token."""
    client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer valid.test.token'
    return client


@pytest.fixture
def minimal_png() -> bytes:
    """A minimal valid mock fundus image with dark vignette border (passes is_fundus_image)."""
    import io
    from PIL import Image, ImageDraw
    buf = io.BytesIO()
    img = Image.new('RGB', (64, 64), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([14, 14, 50, 50], fill=(160, 90, 70))
    img.save(buf, format='PNG')
    return buf.getvalue()
