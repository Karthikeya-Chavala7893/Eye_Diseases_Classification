"""
backend/config.py
─────────────────
Single source of truth for all runtime configuration.

Responsibilities
────────────────
  * Read every tunable value from the process environment (12-factor).
  * Provide typed, documented constants so no other module contains magic numbers.
  * Fail fast at WSGI boot if a mandatory variable is missing (never lazily at
    request time).

Hard constraints honoured (restructure spec §5.3):
  * #23 — environment validated at startup, not at first use.
  * #24 — no magic numbers anywhere else in the codebase.

This module MUST NOT import flask, firebase_admin, torch or transformers so it
can be imported by any layer (including tooling and tests) with zero cost.
"""

import logging
import os

from dotenv import load_dotenv

# Load backend/.env (if present) before any os.environ read below.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, '.env'))


# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger('visionai')


def _csv_env(name: str, default: str) -> list[str]:
    """Parse a comma-separated environment variable into a stripped, non-empty list.

    Args:
        name: Environment variable name.
        default: Fallback value used when the variable is unset.

    Returns:
        List of trimmed string entries with empty items removed.
    """
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


class Config:
    """Immutable application configuration resolved from the environment."""

    # ── Paths ────────────────────────────────────────────────────────────────
    BASE_DIR = _BASE_DIR

    # ── Flask core ───────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    IS_DEVELOPMENT = FLASK_ENV.lower() == 'development'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')

    #: Minimum SECRET_KEY length (128-bit equivalent) enforced by validate_config().
    MIN_SECRET_KEY_LENGTH = 16

    # ── CORS ─────────────────────────────────────────────────────────────────
    #: Explicit origin whitelist — the wildcard is forbidden (constraint #5).
    ALLOWED_ORIGINS = _csv_env(
        'ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000'
    )

    # ── Firebase Admin SDK ───────────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH = os.environ.get(
        'FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json'
    )
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET', '')

    #: Verifying revocation costs an extra Firestore round-trip per request.
    #: Disabled by default for latency (constraint #28); enable in high-security
    #: deployments via CHECK_TOKEN_REVOKED=true.
    CHECK_TOKEN_REVOKED = os.environ.get('CHECK_TOKEN_REVOKED', 'false').lower() == 'true'

    # ── AI inference ─────────────────────────────────────────────────────────
    LOCAL_MODEL_ID = os.environ.get('LOCAL_MODEL_ID', 'NeuronZero/EyeDiseaseClassifier')
    TORCH_DEVICE = os.environ.get('TORCH_DEVICE', 'cpu')
    #: Cold-start budget for model download + initialisation (constraint #25).
    MODEL_LOAD_TIMEOUT_SECONDS = int(os.environ.get('MODEL_LOAD_TIMEOUT_SECONDS', '60'))

    # ── Home screening model ─────────────────────────────────────────────────
    #: Option 1: Use calibrated optical computer vision engine (default, 0 MB, fastest).
    #: When true, optionally queries the secondary ML classifier.
    USE_HOME_AI_MODEL = os.environ.get('USE_HOME_AI_MODEL', 'true').lower() == 'true'

    #: HuggingFace model id for the Daily Home Mode image classifier.
    #: Separate from LOCAL_MODEL_ID so the clinical and home pipelines can be
    #: configured independently (e.g. swap clinical to a local checkpoint while
    #: keeping NeuronZero for home).
    HOME_MODEL_ID = os.environ.get('HOME_MODEL_ID', 'NeuronZero/EyeDiseaseClassifier')

    #: Minimum top-class confidence from the home model to trust as "Normal".
    #: Below this, the model's output is blended with pixel cues instead of
    #: producing a definitive "Healthy" result.
    HOME_MODEL_CONFIDENCE_THRESHOLD = float(
        os.environ.get('HOME_MODEL_CONFIDENCE_THRESHOLD', '0.40')
    )

    #: The label the home model emits for a healthy eye.
    HOME_HEALTHY_LABEL = os.environ.get('HOME_HEALTHY_LABEL', 'Normal')

    # ── Upload validation ────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024          # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
    ALLOWED_MIME_TYPES = {
        'image/png', 'image/jpeg', 'image/jpg',
        'image/bmp', 'image/tiff', 'image/webp',
    }

    # ── Rate limiting ────────────────────────────────────────────────────────
    DEFAULT_RATE_LIMITS = _csv_env('DEFAULT_RATE_LIMITS', '200 per day,50 per hour')
    PREDICT_RATE_LIMIT = os.environ.get('PREDICT_RATE_LIMIT', '10 per minute')
    USER_SYNC_RATE_LIMIT = os.environ.get('USER_SYNC_RATE_LIMIT', '20 per hour')
    SCANS_RATE_LIMIT = os.environ.get('SCANS_RATE_LIMIT', '60 per hour')
    ADMIN_RATE_LIMIT = os.environ.get('ADMIN_RATE_LIMIT', '60 per minute')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

    # ── Firestore query bounds ───────────────────────────────────────────────
    SCAN_HISTORY_DEFAULT_LIMIT = 10
    SCAN_HISTORY_MAX_LIMIT = 50

    # ── Firestore collections ────────────────────────────────────────────────
    USERS_COLLECTION = 'users'
    SCANS_COLLECTION = 'scans'

    # ── Admin ────────────────────────────────────────────────────────────────
    #: Comma-separated emails auto-promoted to admin on first user sync.
    ADMIN_EMAILS = _csv_env('ADMIN_EMAILS', '')

    @classmethod
    def firebase_credentials_abspath(cls) -> str:
        """Resolve FIREBASE_CREDENTIALS_PATH against the backend directory.

        Returns:
            Absolute filesystem path to the service-account JSON key. Relative
            values are resolved against ``backend/``; absolute values pass through.
        """
        path = cls.FIREBASE_CREDENTIALS_PATH
        return path if os.path.isabs(path) else os.path.join(cls.BASE_DIR, path)


def validate_config(config_obj=Config) -> None:
    """Validate that every mandatory configuration variable is present and sane.

    Checks performed:
      * All keys in ``required_keys`` are non-empty.
      * ``SECRET_KEY`` meets the minimum entropy length.
      * ``ALLOWED_ORIGINS`` is non-empty and contains no wildcard (constraint #5).
      * The Firebase service-account key file exists on disk.

    Args:
        config_obj: The Config class (or a compatible object) to validate.

    Returns:
        None.

    Raises:
        RuntimeError: If any required variable is missing, empty or invalid.
            The message enumerates every problem found, not just the first.
    """
    required_keys = ['SECRET_KEY', 'FIREBASE_CREDENTIALS_PATH']
    errors: list[str] = []

    for key in required_keys:
        value = getattr(config_obj, key, None)
        if not value or not str(value).strip():
            errors.append(
                f"  - {key} is missing or empty. Set it in backend/.env or the environment."
            )

    secret_key = (getattr(config_obj, 'SECRET_KEY', '') or '').strip()
    min_len = getattr(config_obj, 'MIN_SECRET_KEY_LENGTH', 16)
    if secret_key and len(secret_key) < min_len:
        errors.append(
            f"  - SECRET_KEY is too short (minimum {min_len} characters). "
            "Use a high-entropy random string."
        )

    origins = getattr(config_obj, 'ALLOWED_ORIGINS', []) or []
    if not origins:
        errors.append(
            "  - ALLOWED_ORIGINS is empty. Whitelist the frontend origin "
            "(e.g. http://localhost:3000)."
        )
    if '*' in origins:
        errors.append(
            "  - ALLOWED_ORIGINS must not contain the wildcard entry — "
            "list each trusted origin explicitly."
        )

    creds_path = config_obj.firebase_credentials_abspath()
    if not os.path.isfile(creds_path):
        errors.append(
            f"  - Firebase service-account key not found at '{creds_path}'. "
            "Download it from Firebase Console -> Project Settings -> Service Accounts."
        )

    if errors:
        raise RuntimeError(
            "Critical Configuration Error — the following problems were found:\n"
            + "\n".join(errors)
            + "\n\nHint: copy backend/.env.example to backend/.env and fill in every value."
        )

    if not getattr(config_obj, 'FIREBASE_STORAGE_BUCKET', ''):
        logger.warning(
            "FIREBASE_STORAGE_BUCKET is not set. Firebase Storage features stay disabled."
        )

    logger.info("Environment configuration validated successfully.")
