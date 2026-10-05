"""
backend/db.py
─────────────
Firestore persistence layer.

Single Responsibility
─────────────────────
Every Cloud Firestore document operation lives here. No HTTP, no inference, no
token verification.

Hard constraints honoured (restructure spec §4.4):
  * MUST NOT import flask, model or auth.
  * MUST use firestore.SERVER_TIMESTAMP — never datetime.now().
  * MUST use merge=True on user upserts so existing fields survive.
  * MUST clamp get_scan_history(limit) to Config.SCAN_HISTORY_MAX_LIMIT.
  * MUST NEVER persist raw image bytes, base64 images or image URLs — only a
    SHA-256 digest of the uploaded image.

This module also owns Firebase Admin SDK bootstrapping (``init_firestore``)
because the Firestore client is the only long-lived Firebase handle the backend
keeps. ``auth.py`` relies on the default app this function initialises.
"""

import hashlib
import logging
from datetime import datetime

import firebase_admin
from firebase_admin import credentials as fb_credentials
from firebase_admin import firestore
from google.api_core import exceptions as gcloud_exceptions

from config import Config

logger = logging.getLogger('visionai.db')


class IndexNotReadyError(RuntimeError):
    """Raised when a query needs a composite index that does not exist yet.

    Firestore answers such queries with ``FAILED_PRECONDITION`` and a console
    link. Surfacing a distinct exception lets the API return an actionable 503
    instead of an opaque 500 (see ``firestore.indexes.json``).
    """

#: Cached Firestore client — populated by init_firestore().
_client = None


def init_firestore(credentials_path: str | None = None, storage_bucket: str | None = None) -> None:
    """Initialise the Firebase Admin default app and cache a Firestore client.

    Idempotent: a second call is a no-op. Safe to invoke from every WSGI worker.

    Args:
        credentials_path: Absolute path to the service-account JSON key.
            Defaults to ``Config.firebase_credentials_abspath()``.
        storage_bucket: Firebase Storage bucket name. Defaults to
            ``Config.FIREBASE_STORAGE_BUCKET``. Ignored when empty.

    Returns:
        None.

    Raises:
        RuntimeError: If the credentials file is unreadable or the SDK refuses
            to initialise.
    """
    global _client

    if _client is not None:
        return

    creds_path = credentials_path or Config.firebase_credentials_abspath()
    bucket = storage_bucket if storage_bucket is not None else Config.FIREBASE_STORAGE_BUCKET

    try:
        if not firebase_admin._apps:  # noqa: SLF001 — documented public-enough registry
            cred = fb_credentials.Certificate(creds_path)
            options = {'storageBucket': bucket} if bucket else None
            firebase_admin.initialize_app(cred, options)
            logger.info("Firebase Admin SDK initialised. Project: %s", cred.project_id)
        _client = firestore.client()
    except Exception as exc:  # noqa: BLE001 — re-raised as RuntimeError below
        logger.error("Firebase initialisation failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Firebase initialisation failed: {exc}") from exc


def is_connected() -> bool:
    """Report whether a Firestore client has been initialised.

    Args:
        None.

    Returns:
        True when ``init_firestore()`` has completed successfully.
    """
    return _client is not None


def _require_client():
    """Return the cached Firestore client or fail loudly.

    Args:
        None.

    Returns:
        The initialised ``google.cloud.firestore.Client``.

    Raises:
        RuntimeError: If ``init_firestore()`` has not been called yet.
    """
    if _client is None:
        raise RuntimeError("Firestore client is not initialised — call init_firestore() first")
    return _client


def _to_iso(value) -> str | None:
    """Normalise a Firestore timestamp into an ISO-8601 string.

    Args:
        value: A ``datetime``, a Firestore ``DatetimeWithNanoseconds``, None, or
            a sentinel that has not yet been resolved server-side.

    Returns:
        ISO-8601 string, or None when the value is absent or not a datetime.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    isoformat = getattr(value, 'isoformat', None)
    return isoformat() if callable(isoformat) else None


def upsert_user(uid: str, email: str, display_name: str, login_method: str) -> bool:
    """Create or update a user profile document keyed by Firebase Auth UID.

    ``createdAt`` is written only when the document does not yet exist, so the
    original signup timestamp is never overwritten. Passwords and password
    hashes are NEVER stored — Firebase Auth owns credentials (constraint #7).

    Args:
        uid: Firebase Auth UID; used verbatim as the Firestore document ID.
        email: User email address (stored lowercase).
        display_name: Human-readable name from the verified JWT claims.
        login_method: Either ``'email'`` or ``'google'``.

    Returns:
        True when the document was newly created, False when an existing
        document was merged into.

    Raises:
        RuntimeError: If Firestore is not initialised.
        Exception: Re-raises any Firestore write error after logging it.
    """
    client = _require_client()
    doc_ref = client.collection(Config.USERS_COLLECTION).document(uid)

    try:
        snapshot = doc_ref.get()
        is_new = not getattr(snapshot, 'exists', False)

        payload = {
            'uid': uid,
            'email': (email or '').lower(),
            'displayName': display_name,
            'loginMethod': login_method,
            'lastLogin': firestore.SERVER_TIMESTAMP,
        }
        if is_new:
            payload['createdAt'] = firestore.SERVER_TIMESTAMP

        doc_ref.set(payload, merge=True)
        logger.info("User profile %s: %s", 'created' if is_new else 'updated', uid)
        return is_new
    except Exception as exc:
        logger.error("Firestore user upsert failed for uid=%s: %s", uid, exc)
        raise


def get_user(uid: str) -> dict | None:
    """Fetch a single user profile document.

    Args:
        uid: Firebase Auth UID (the Firestore document ID).

    Returns:
        The document as a dict with timestamps normalised to ISO-8601 strings,
        or None when no such document exists.

    Raises:
        RuntimeError: If Firestore is not initialised.
    """
    client = _require_client()
    snapshot = client.collection(Config.USERS_COLLECTION).document(uid).get()
    if not getattr(snapshot, 'exists', False):
        return None

    data = snapshot.to_dict() or {}
    return {
        **data,
        'createdAt': _to_iso(data.get('createdAt')),
        'lastLogin': _to_iso(data.get('lastLogin')),
    }


def save_scan(
    uid: str,
    predictions: list[dict],
    image_bytes: bytes,
    model_id: str | None = None,
) -> str:
    """Persist one screening result.

    Stores the prediction payload plus a SHA-256 digest of the uploaded image
    for de-duplication analytics. The image itself is never written anywhere
    (constraint #7 / privacy rule §4.4).

    Args:
        uid: Firebase Auth UID of the scanning user.
        predictions: Sorted prediction list from ``model.predict()`` or
            ``triage.assess()``.
        image_bytes: Raw uploaded bytes; hashed, then discarded. Home Mode
            screenings without a photo pass ``b''``.
        model_id: Engine that produced ``predictions``. Defaults to the
            configured clinical model, so existing callers are unaffected.

    Returns:
        The auto-generated Firestore document ID.

    Raises:
        ValueError: If ``predictions`` is empty.
        RuntimeError: If Firestore is not initialised.
        Exception: Re-raises any Firestore write error after logging it.
    """
    if not predictions:
        raise ValueError("predictions must contain at least one entry")

    client = _require_client()
    top = predictions[0]

    document = {
        'uid': uid,
        'timestamp': firestore.SERVER_TIMESTAMP,
        'primaryLabel': top.get('label'),
        'confidence': top.get('confidence'),
        'allResults': predictions,
        'modelId': model_id or Config.LOCAL_MODEL_ID,
        'imageHash': hashlib.sha256(image_bytes).hexdigest(),
    }

    try:
        _, doc_ref = client.collection(Config.SCANS_COLLECTION).add(document)
        scan_id = getattr(doc_ref, 'id', '')
        logger.info("Scan persisted for uid=%s doc=%s", uid, scan_id)
        return scan_id
    except Exception as exc:
        logger.error("Firestore scan write failed for uid=%s: %s", uid, exc)
        raise


def get_scan_history(uid: str, limit: int = Config.SCAN_HISTORY_DEFAULT_LIMIT) -> list[dict]:
    """Retrieve a user's most recent scans, newest first.

    Requires the composite Firestore index ``scans(uid ASC, timestamp DESC)``.

    Args:
        uid: Firebase Auth UID whose scans should be returned.
        limit: Maximum number of documents. Clamped here (not by the caller) to
            the range 1..``Config.SCAN_HISTORY_MAX_LIMIT``.

    Returns:
        List of scan dicts, each including its document ``id`` and an ISO-8601
        ``timestamp``. Empty list when the user has no scans.

    Raises:
        RuntimeError: If Firestore is not initialised.
        IndexNotReadyError: If the composite index has not been created or is
            still building.
    """
    client = _require_client()

    try:
        safe_limit = int(limit)
    except (TypeError, ValueError):
        safe_limit = Config.SCAN_HISTORY_DEFAULT_LIMIT
    safe_limit = max(1, min(safe_limit, Config.SCAN_HISTORY_MAX_LIMIT))

    query = (
        client.collection(Config.SCANS_COLLECTION)
        .where(filter=firestore.FieldFilter('uid', '==', uid))
        .order_by('timestamp', direction=firestore.Query.DESCENDING)
        .limit(safe_limit)
    )

    try:
        snapshots = query.get()
    except gcloud_exceptions.FailedPrecondition as exc:
        logger.error(
            "Scan history query needs the composite index scans(uid ASC, timestamp DESC). "
            "Deploy firestore.indexes.json or follow the console link in: %s", exc,
        )
        raise IndexNotReadyError(
            'Scan history index is not ready yet. Deploy firestore.indexes.json '
            '(firebase deploy --only firestore:indexes) and retry in a few minutes.'
        ) from exc

    scans: list[dict] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        scans.append({
            'id': getattr(snapshot, 'id', ''),
            'primaryLabel': data.get('primaryLabel'),
            'confidence': data.get('confidence'),
            'allResults': data.get('allResults', []),
            'modelId': data.get('modelId'),
            'imageHash': data.get('imageHash'),
            'timestamp': _to_iso(data.get('timestamp')),
        })
    return scans


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN OPERATIONS
# ═════════════════════════════════════════════════════════════════════════════

def list_all_users(limit: int = 50) -> list[dict]:
    """Return all user profiles, newest login first.

    Args:
        limit: Maximum number of users. Clamped to 200.

    Returns:
        List of user profile dicts with ISO-8601 timestamps.
    """
    client = _require_client()
    safe_limit = max(1, min(int(limit), 200))

    query = (
        client.collection(Config.USERS_COLLECTION)
        .order_by('lastLogin', direction=firestore.Query.DESCENDING)
        .limit(safe_limit)
    )
    users: list[dict] = []
    for snapshot in query.get():
        data = snapshot.to_dict() or {}
        users.append({
            'uid': getattr(snapshot, 'id', ''),
            'email': data.get('email', ''),
            'displayName': data.get('displayName', ''),
            'loginMethod': data.get('loginMethod', ''),
            'role': data.get('role', 'user'),
            'createdAt': _to_iso(data.get('createdAt')),
            'lastLogin': _to_iso(data.get('lastLogin')),
        })
    return users


def list_all_scans(limit: int = 50) -> list[dict]:
    """Return all scans across every user, newest first.

    Args:
        limit: Maximum number of scans. Clamped to 200.

    Returns:
        List of scan dicts including the owning UID.
    """
    client = _require_client()
    safe_limit = max(1, min(int(limit), 200))

    query = (
        client.collection(Config.SCANS_COLLECTION)
        .order_by('timestamp', direction=firestore.Query.DESCENDING)
        .limit(safe_limit)
    )
    scans: list[dict] = []
    for snapshot in query.get():
        data = snapshot.to_dict() or {}
        scans.append({
            'id': getattr(snapshot, 'id', ''),
            'uid': data.get('uid', ''),
            'primaryLabel': data.get('primaryLabel'),
            'confidence': data.get('confidence'),
            'allResults': data.get('allResults', []),
            'modelId': data.get('modelId'),
            'imageHash': data.get('imageHash'),
            'timestamp': _to_iso(data.get('timestamp')),
        })
    return scans


def get_platform_stats() -> dict:
    """Aggregate platform-wide statistics for the admin dashboard.

    Returns:
        Dict with ``totalUsers``, ``totalScans``, ``diseaseDistribution``
        (label → count mapping for pie charts), and ``userGrowth`` metadata.
    """
    client = _require_client()

    # Count users
    user_snapshots = list(client.collection(Config.USERS_COLLECTION).stream())
    total_users = len(user_snapshots)

    # Count scans and build disease distribution
    scan_snapshots = list(client.collection(Config.SCANS_COLLECTION).stream())
    total_scans = len(scan_snapshots)

    disease_counts: dict[str, int] = {}
    for snapshot in scan_snapshots:
        data = snapshot.to_dict() or {}
        label = data.get('primaryLabel', 'Unknown')
        disease_counts[label] = disease_counts.get(label, 0) + 1

    # Count users by login method for the patient pie chart
    login_method_counts: dict[str, int] = {}
    for snapshot in user_snapshots:
        data = snapshot.to_dict() or {}
        method = data.get('loginMethod', 'unknown')
        login_method_counts[method] = login_method_counts.get(method, 0) + 1

    return {
        'totalUsers': total_users,
        'totalScans': total_scans,
        'diseaseDistribution': disease_counts,
        'loginMethodDistribution': login_method_counts,
    }


def set_admin_claim(uid: str) -> None:
    """Grant the ``admin`` custom claim to a Firebase Auth user.

    Args:
        uid: Firebase Auth UID to promote.

    Raises:
        Exception: If the Firebase Admin SDK call fails.
    """
    from firebase_admin import auth as fb_auth
    fb_auth.set_custom_user_claims(uid, {'admin': True})

    # Also mark the role in Firestore for display purposes
    client = _require_client()
    client.collection(Config.USERS_COLLECTION).document(uid).set(
        {'role': 'admin'}, merge=True,
    )
    logger.info("Admin claim granted to uid=%s", uid)
