"""
backend/app.py
──────────────
VisionAI REST API — a pure JSON WSGI application.

Role
────
Routing, middleware and error handling only. Every unit of real work is
delegated:
    config.py  -> environment resolution + fail-fast validation
    model.py   -> EfficientNetB0 inference
    triage.py  -> rule-based Daily Home Mode scoring (no ML)
    db.py      -> Firestore persistence
    auth.py    -> Firebase JWT verification

Hard constraints honoured (restructure spec §4.2 / §5.2):
  * #14 — never calls render_template(), send_file() or send_from_directory().
  * #18 — every route is namespaced under /api/.
  * #21 — every response body is {"success": bool, "data"?: T, "error"?: str}.
  * Zero server-side sessions, zero password handling, zero CSRF tokens
    (irrelevant to a stateless Bearer-token API per RFC 6750).

Endpoints
─────────
    POST /api/predict      Bearer   multipart/form-data
                                    { mode?: 'clinical'|'home',
                                      image: File (required in clinical mode,
                                             optional in home mode),
                                      symptoms?: JSON array of symptom ids }
    GET  /api/health       public
    GET  /api/config       public
    POST /api/user/sync    Bearer   {}
    GET  /api/user/scans   Bearer   ?limit=10
"""

import json
import logging

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

import db
import model
import home_model
import triage
from auth import require_admin, require_auth
from config import Config, validate_config

logger = logging.getLogger('visionai.api')

#: URL namespace for every route (constraint #18).
API_PREFIX = '/api'

#: Clinical RETFound scan of a fundus/OCT image — the original behaviour.
MODE_CLINICAL = 'clinical'

#: Daily Home Mode: smartphone photo + symptom checklist, scored by triage.py.
MODE_HOME = 'home'

#: Modes ``/api/predict`` accepts; anything else is a 400.
SCREENING_MODES = (MODE_CLINICAL, MODE_HOME)

#: Pseudo-model id reported for home screenings so history rows stay honest
#: about the fact that no neural network was involved.
HOME_ENGINE_ID = 'rule-based-triage-v1'

#: Engine id reported when the NeuronZero model was used for home screening.
HOME_ENGINE_ID_AI = 'neuronzero-triage-v2'


# ═════════════════════════════════════════════════════════════════════════════
# RESPONSE ENVELOPE (constraint #21)
# ═════════════════════════════════════════════════════════════════════════════

def ok(data, status: int = 200):
    """Build a success envelope.

    Args:
        data: JSON-serialisable payload placed under the ``data`` key.
        status: HTTP status code, default 200.

    Returns:
        Tuple of (Flask JSON response, status code).
    """
    return jsonify({'success': True, 'data': data}), status


def fail(message: str, status: int):
    """Build a sanitised error envelope.

    Never includes stack traces, filesystem paths or internal identifiers
    (constraint #3 / OWASP A09:2021).

    Args:
        message: Client-safe error description.
        status: HTTP status code.

    Returns:
        Tuple of (Flask JSON response, status code).
    """
    return jsonify({'success': False, 'error': message}), status


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION FACTORY-STYLE BOOTSTRAP
# ═════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config.from_object(Config)

# Trust reverse-proxy headers so rate limiting and audit logs see the real IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Explicit origin whitelist — no wildcard (constraint #5). Bearer tokens travel
# in a header, so cookie credentials are neither needed nor allowed.
CORS(
    app,
    resources={rf"{API_PREFIX}/*": {"origins": Config.ALLOWED_ORIGINS}},
    supports_credentials=False,
    allow_headers=['Authorization', 'Content-Type'],
    methods=['GET', 'POST', 'OPTIONS'],
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=Config.DEFAULT_RATE_LIMITS,
    storage_uri=Config.RATELIMIT_STORAGE_URI,
)

# Fail fast before any dependent initialisation (constraint #23).
validate_config(Config)


def init_services() -> None:
    """Initialise Firebase and load the AI model once per WSGI worker.

    Failures are logged but never fatal: ``/api/health`` reports degraded
    subsystems and ``/api/predict`` returns 503 while the model is unavailable,
    which keeps the health endpoint reachable for orchestrators.

    Args:
        None.

    Returns:
        None.
    """
    try:
        db.init_firestore()
    except RuntimeError:
        logger.error("Firestore unavailable — user sync and scan history are degraded.")

    try:
        model.load_model()
    except RuntimeError:
        logger.error("AI model unavailable — /api/predict will return 503.")

    try:
        home_model.load_home_model()
    except RuntimeError:
        logger.warning(
            "Home screening model unavailable — home mode will use pixel cues only."
        )


# ═════════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS (OWASP A05:2021)
# ═════════════════════════════════════════════════════════════════════════════

@app.after_request
def apply_security_headers(response):
    """Inject OWASP-recommended headers on every response.

    The API serves JSON exclusively, so the CSP denies every resource type by
    default — nothing is ever rendered from this origin.

    Args:
        response: The outgoing Flask response.

    Returns:
        The same response with security headers attached.
    """
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none';"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    return response


# ═════════════════════════════════════════════════════════════════════════════
# UPLOAD VALIDATION HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _validate_upload(file_storage) -> str | None:
    """Validate an uploaded file against the server-side whitelist.

    Runs independently of any client-side check (constraint #9, defence in depth).

    Args:
        file_storage: The Werkzeug ``FileStorage`` from ``request.files``.

    Returns:
        A client-safe error message, or None when the upload is acceptable.
    """
    if not file_storage or not file_storage.filename:
        return 'Empty file'

    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in Config.ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(Config.ALLOWED_EXTENSIONS))
        return f'Invalid format. Use: {allowed}'

    mimetype = (file_storage.mimetype or '').lower()
    if mimetype and mimetype not in Config.ALLOWED_MIME_TYPES:
        return 'Invalid image content type'

    return None


def _parse_symptoms(raw: str | None) -> list[str]:
    """Parse the ``symptoms`` form field of a Home Mode screening.

    Accepts a JSON array of strings. Unknown ids survive parsing and are
    discarded later by ``triage.assess``, so a stale client degrades instead of
    erroring.

    Args:
        raw: The raw form value, or None when the field was omitted.

    Returns:
        The symptom ids, truncated to ``triage.MAX_SYMPTOMS``.

    Raises:
        ValueError: If the value is present but is not a JSON array of strings.
    """
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('symptoms must be a JSON array of strings') from exc

    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError('symptoms must be a JSON array of strings')

    return parsed[:triage.MAX_SYMPTOMS]


# ═════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route(f'{API_PREFIX}/health')
@limiter.exempt
def health():
    """Liveness and readiness probe.

    Args:
        None.

    Returns:
        200 with ``{status, model_loaded, firebase_connected, model, inference}``.
        The status is 'healthy' only when both subsystems are up.
    """
    model_loaded = model.is_loaded()
    home_loaded = home_model.is_home_model_loaded()
    firebase_connected = db.is_connected()
    return ok({
        'status': 'healthy' if (model_loaded and firebase_connected) else 'degraded',
        'model_loaded': model_loaded,
        'home_model_loaded': home_loaded,
        'use_home_ai_model': Config.USE_HOME_AI_MODEL,
        'firebase_connected': firebase_connected,
        'model': Config.LOCAL_MODEL_ID,
        'inference': 'local',
    })


@app.route(f'{API_PREFIX}/config')
@limiter.exempt
def get_config():
    """Publish the upload limits the frontend must mirror.

    Args:
        None.

    Returns:
        200 with ``{maxFileSizeBytes, allowedMimeTypes, allowedExtensions,
        model, inference, modelLoaded}``.
    """
    return ok({
        'maxFileSizeBytes': Config.MAX_CONTENT_LENGTH,
        'allowedMimeTypes': sorted(Config.ALLOWED_MIME_TYPES),
        'allowedExtensions': sorted(Config.ALLOWED_EXTENSIONS),
        'model': Config.LOCAL_MODEL_ID,
        'inference': 'local',
        'modelLoaded': model.is_loaded(),
    })


@app.route(f'{API_PREFIX}/predict', methods=['POST'])
@limiter.limit(Config.PREDICT_RATE_LIMIT)
@require_auth
def predict():
    """Run one screening in either Clinical or Daily Home mode.

    Mode routing (dual-mode gateway):

      * ``clinical`` (default) — an uploaded retinal fundus/OCT image is read
        into memory, classified by the RETFound model, hashed and discarded.
        Behaviour is byte-for-byte the original single-mode implementation.
      * ``home`` — a symptom checklist, optionally accompanied by a smartphone
        photo, is scored by the rule engine in ``triage.py``. The AI model is
        never touched, so this path stays available even while the model is
        cold or unavailable.

    Neither mode writes an image to disk or persists one (constraint #2).

    Args:
        None. Reads ``mode``, ``image`` and ``symptoms`` from
        multipart/form-data and the caller identity from the verified JWT via
        ``flask.g``.

    Returns:
        200 with ``{predictions, mode, model, inference, user, cues?}``.
        400 when the mode is unknown, the upload is missing/undecodable, or a
            home screening reports nothing scoreable.
        401 when the Bearer token is absent or invalid (handled by @require_auth).
        413 when the payload exceeds MAX_CONTENT_LENGTH (handled by errorhandler).
        429 when the caller exceeds PREDICT_RATE_LIMIT.
        503 when the AI model is not loaded (clinical mode only).
    """
    mode = (request.form.get('mode') or MODE_CLINICAL).strip().lower()
    if mode not in SCREENING_MODES:
        return fail(f"Unknown mode '{mode}'. Use 'clinical' or 'home'.", 400)

    # ── Read the upload, if any. Home mode tolerates its absence. ───────────
    image_bytes = b''
    if 'image' in request.files and request.files['image'].filename:
        file_storage = request.files['image']
        validation_error = _validate_upload(file_storage)
        if validation_error:
            return fail(validation_error, 400)
        image_bytes = file_storage.read()
        if not image_bytes:
            return fail('Empty file', 400)

    if mode == MODE_HOME:
        return _screen_home(image_bytes)
    return _screen_clinical(image_bytes)


def _screen_clinical(image_bytes: bytes):
    """Classify a retinal image with the RETFound model. See :func:`predict`."""
    if not model.is_loaded():
        return fail('AI model unavailable', 503)

    if not image_bytes:
        return fail('No image uploaded', 400)

    # Guard: reject clearly non-fundus images before running the expensive model.
    # This prevents misleading predictions on exterior eye photos, selfies, etc.
    if not model.is_fundus_image(image_bytes):
        logger.info(
            "Clinical upload rejected (not a fundus image) for uid=%s", g.uid
        )
        return fail(
            'This AI model requires a colour retinal fundus photograph — a specialised clinical '
            'photograph of the retina taken with a fundus camera. Grayscale OCT scans, regular eye photos '
            'or selfies will not produce accurate results. Please upload a valid colour fundus image.',
            400,
        )

    try:
        predictions = model.predict(image_bytes)
    except ValueError as exc:
        logger.warning("Invalid image upload from uid=%s: %s", g.uid, exc)
        return fail(
            'Invalid or corrupted image format. Please upload a valid JPEG/PNG image.', 400
        )
    except RuntimeError:
        logger.error("Inference requested while model unloaded (uid=%s)", g.uid)
        return fail('AI model unavailable', 503)
    except Exception:  # noqa: BLE001 — sanitise everything else
        logger.exception("Prediction failed for uid=%s", g.uid)
        return fail('An error occurred while processing the image. Please try again.', 500)

    logger.info(
        "Prediction for uid=%s: %s (%.2f%%)",
        g.uid, predictions[0]['label'], predictions[0]['confidence'],
    )

    _persist(predictions, image_bytes)

    return ok({
        'predictions': predictions,
        'mode': MODE_CLINICAL,
        'model': Config.LOCAL_MODEL_ID,
        'inference': 'local',
        'user': g.display_name,
    })


def _screen_home(image_bytes: bytes):
    """Score a home screening with the triage engine, optionally augmented by
    the NeuronZero AI model.  See :func:`predict`.

    Pipeline:
      1. Parse symptoms from the form.
      2. Guard against fundus images (belong in clinical mode).
      3. Extract pixel-level colour cues (fast, CPU, always runs).
      4. Run NeuronZero model if available (may return []).
      5. Score with all evidence combined via ``assess_with_model``
         (falls back to ``assess`` when the model is unavailable).
    """
    try:
        symptoms = _parse_symptoms(request.form.get('symptoms'))
    except ValueError as exc:
        return fail(str(exc), 400)

    # Guard: if the optional photo looks like a fundus scan, it belongs in Clinical mode.
    if image_bytes and model.is_fundus_image(image_bytes):
        logger.info(
            "Home triage photo looks like a fundus image for uid=%s — suggesting clinical mode",
            g.uid,
        )
        return fail(
            'The photo you uploaded appears to be a retinal fundus image. '
            'Please switch to Clinical Retinal Scan mode (🏥) to analyse it with our AI model. '
            'Home mode is for regular close-up smartphone photos of your eye.',
            400,
        )

    # Step 3: Pixel-level colour cues (always available, zero ML cost)
    cues = triage.inspect_image(image_bytes) if image_bytes else {}

    # Step 4: Optional home AI model (Option 1 uses calibrated optical engine by default;
    # secondary model can be enabled via USE_HOME_AI_MODEL=true).
    model_predictions = []
    home_model_used = False
    if Config.USE_HOME_AI_MODEL and image_bytes and home_model.is_home_model_loaded():
        model_predictions = home_model.predict_home(image_bytes)
        home_model_used = bool(model_predictions)

    # Step 5: Score with all evidence combined
    try:
        if model_predictions:
            predictions = triage.assess_with_model(symptoms, cues, model_predictions)
        else:
            predictions = triage.assess(symptoms, cues)
    except ValueError:
        return fail(
            'Select at least one symptom, or add a photo, so we have something to assess.',
            400,
        )

    engine_id = HOME_ENGINE_ID_AI if home_model_used else HOME_ENGINE_ID

    logger.info(
        "Home triage for uid=%s: %s (%.2f%% match, %d symptom(s), model=%s)",
        g.uid, predictions[0]['label'], predictions[0]['confidence'],
        len(symptoms), home_model_used,
    )

    _persist(predictions, image_bytes, model_id=engine_id)

    return ok({
        'predictions': predictions,
        'mode': MODE_HOME,
        'model': engine_id,
        'inference': 'local',
        'user': g.display_name,
        'cues': cues,
        'home_model_used': home_model_used,
    })


def _persist(predictions: list[dict], image_bytes: bytes, model_id: str | None = None) -> None:
    """Best-effort scan-history write — a Firestore outage never fails a screening."""
    try:
        db.save_scan(g.uid, predictions, image_bytes, model_id=model_id)
    except Exception:  # noqa: BLE001
        logger.warning("Scan history write skipped for uid=%s (Firestore unavailable)", g.uid)


@app.route(f'{API_PREFIX}/user/sync', methods=['POST'])
@limiter.limit(Config.USER_SYNC_RATE_LIMIT)
@require_auth
def user_sync():
    """Upsert the caller's Firestore profile from their verified JWT claims.

    The client sends an empty body — every field is taken from the token, so a
    caller can never claim another user's UID (constraint #6).

    Args:
        None.

    Returns:
        200 with ``{uid, created}`` where ``created`` is True on first sync.
        503 when Firestore is unavailable.
    """
    try:
        created = db.upsert_user(
            uid=g.uid,
            email=g.email,
            display_name=g.display_name,
            login_method=g.login_method,
        )
    except RuntimeError:
        return fail('User store unavailable', 503)
    except Exception:  # noqa: BLE001
        logger.exception("User sync failed for uid=%s", g.uid)
        return fail('Failed to synchronise user profile', 500)

    return ok({'uid': g.uid, 'created': created})


@app.route(f'{API_PREFIX}/user/scans')
@limiter.limit(Config.SCANS_RATE_LIMIT)
@require_auth
def user_scans():
    """Return the caller's recent screening history, newest first.

    Args:
        None. Reads the optional ``limit`` query parameter (default 10, hard
        maximum 50 enforced inside ``db.get_scan_history``).

    Returns:
        200 with ``{scans, total}``.
        503 when Firestore is unavailable.
    """
    raw_limit = request.args.get('limit', Config.SCAN_HISTORY_DEFAULT_LIMIT)
    try:
        scans = db.get_scan_history(g.uid, raw_limit)
    except db.IndexNotReadyError as exc:
        return fail(str(exc), 503)
    except RuntimeError:
        return fail('User store unavailable', 503)
    except Exception:  # noqa: BLE001
        logger.exception("Scan history read failed for uid=%s", g.uid)
        return fail('Failed to load scan history', 500)

    return ok({'scans': scans, 'total': len(scans)})


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route(f'{API_PREFIX}/admin/verify')
@limiter.limit(Config.ADMIN_RATE_LIMIT)
@require_auth
def admin_verify():
    """Check whether the authenticated caller has admin privileges.

    Returns:
        200 with ``{isAdmin, uid, email}`` — ``isAdmin`` is always true or
        the caller receives a non-200 from ``@require_auth``.
    """
    return ok({
        'isAdmin': getattr(g, 'is_admin', False),
        'uid': g.uid,
        'email': g.email,
    })


@app.route(f'{API_PREFIX}/admin/stats')
@limiter.limit(Config.ADMIN_RATE_LIMIT)
@require_auth
@require_admin
def admin_stats():
    """Return platform-wide statistics for the admin dashboard.

    Returns:
        200 with ``{totalUsers, totalScans, diseaseDistribution,
        loginMethodDistribution, model}``.
    """
    try:
        stats = db.get_platform_stats()
    except RuntimeError:
        return fail('Admin store unavailable', 503)
    except Exception:  # noqa: BLE001
        logger.exception("Admin stats query failed for uid=%s", g.uid)
        return fail('Failed to load platform statistics', 500)

    stats['model'] = Config.LOCAL_MODEL_ID
    return ok(stats)


@app.route(f'{API_PREFIX}/admin/users')
@limiter.limit(Config.ADMIN_RATE_LIMIT)
@require_auth
@require_admin
def admin_users():
    """Return all registered user profiles.

    Returns:
        200 with ``{users, total}``.
    """
    raw_limit = request.args.get('limit', 50)
    try:
        users = db.list_all_users(int(raw_limit))
    except RuntimeError:
        return fail('Admin store unavailable', 503)
    except Exception:  # noqa: BLE001
        logger.exception("Admin users query failed for uid=%s", g.uid)
        return fail('Failed to load users', 500)

    return ok({'users': users, 'total': len(users)})


@app.route(f'{API_PREFIX}/admin/scans')
@limiter.limit(Config.ADMIN_RATE_LIMIT)
@require_auth
@require_admin
def admin_scans():
    """Return all scans across every user.

    Returns:
        200 with ``{scans, total}``.
    """
    raw_limit = request.args.get('limit', 50)
    try:
        scans = db.list_all_scans(int(raw_limit))
    except RuntimeError:
        return fail('Admin store unavailable', 503)
    except Exception:  # noqa: BLE001
        logger.exception("Admin scans query failed for uid=%s", g.uid)
        return fail('Failed to load scans', 500)

    return ok({'scans': scans, 'total': len(scans)})


@app.route(f'{API_PREFIX}/admin/promote', methods=['POST'])
@limiter.limit(Config.ADMIN_RATE_LIMIT)
@require_auth
@require_admin
def admin_promote():
    """Promote a user to admin by email.

    Body:
        ``{"email": "user@example.com"}``

    Returns:
        200 with ``{email, uid, promoted: true}``.
        400 when the email is missing or the user is not found.
    """
    from firebase_admin import auth as fb_auth

    body = request.get_json(silent=True) or {}
    email = (body.get('email') or '').strip().lower()
    if not email:
        return fail('Email is required', 400)

    try:
        target_user = fb_auth.get_user_by_email(email)
    except fb_auth.UserNotFoundError:
        return fail(f'No user found with email: {email}', 404)
    except Exception:  # noqa: BLE001
        logger.exception("Admin promote lookup failed for email=%s", email)
        return fail('Failed to look up user', 500)

    try:
        db.set_admin_claim(target_user.uid)
    except Exception:  # noqa: BLE001
        logger.exception("Admin promote failed for uid=%s", target_user.uid)
        return fail('Failed to promote user', 500)

    logger.info("Admin %s promoted %s to admin", g.uid, target_user.uid)
    return ok({'email': email, 'uid': target_user.uid, 'promoted': True})



# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═════════════════════════════════════════════════════════════════════════════

@app.errorhandler(400)
def handle_bad_request(error):
    """Return a JSON 400 for malformed requests."""
    return fail('Bad request', 400)


@app.errorhandler(401)
def handle_unauthorized(error):
    """Return a JSON 401 — this API never redirects to a login page."""
    return fail('Authentication required', 401)


@app.errorhandler(404)
def handle_not_found(error):
    """Return a JSON 404 for unknown routes."""
    return fail('Not found', 404)


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Return a JSON 405 for unsupported HTTP verbs."""
    return fail('Method not allowed', 405)


@app.errorhandler(429)
def handle_rate_limit(error):
    """Return a JSON 429 including the limit that was tripped."""
    return fail(f'Rate limit exceeded. {error.description}', 429)


@app.errorhandler(500)
def handle_server_error(error):
    """Return a sanitised JSON 500 — never a stack trace."""
    return fail('Internal server error', 500)


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_payload_too_large(error):
    """RFC 7807 Problem Details response for oversized uploads.

    Werkzeug raises RequestEntityTooLarge before the body is fully read, so the
    WSGI server terminates the stream early — no memory is wasted buffering the
    rejected payload.

    Args:
        error: The raised exception.

    Returns:
        413 with both the RFC 7807 members and the standard success/error
        envelope, so generic clients and problem-aware clients both work.
    """
    max_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)
    logger.warning("Upload rejected — payload too large (limit %dMB) path=%s", max_mb, request.path)
    return jsonify({
        'type': 'https://visionai.org/errors/payload-too-large',
        'title': 'Payload Too Large',
        'status': 413,
        'detail': f'Uploaded file exceeds the maximum allowed size of {max_mb}MB.',
        'instance': request.path,
        'success': False,
        'error': f'File size exceeds maximum limit of {max_mb}MB. Please select a smaller image.',
    }), 413


# ═════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═════════════════════════════════════════════════════════════════════════════

# Executed at import time so Gunicorn workers warm up before serving traffic
# (constraint #30). Tests patch firebase_admin and transformers beforehand.
init_services()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=Config.IS_DEVELOPMENT)
