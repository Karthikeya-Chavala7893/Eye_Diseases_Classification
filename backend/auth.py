"""
backend/auth.py
───────────────
Firebase JWT verification middleware.

Single Responsibility
─────────────────────
Turn an ``Authorization: Bearer <token>`` header into verified identity claims
on ``flask.g``. No business logic, no Firestore reads, no model calls.

Hard constraints honoured (restructure spec §4.5):
  * MUST NOT import db or model.
  * MUST read the token from the Authorization header ONLY — never from query
    parameters or the request body.
  * MUST distinguish ExpiredIdTokenError from generic InvalidIdTokenError.
  * MUST support revocation checking via check_revoked.
  * MUST log failures at WARNING with the client IP, and NEVER log the token.

Firebase ID tokens are RS256-signed JWTs. ``firebase_admin.auth.verify_id_token``
fetches Google's public x509 certificates (cached ~1h), verifies the signature,
and validates the iss / aud / exp / iat claims against the project.

The Firebase Admin default app must already be initialised (``db.init_firestore``
does this at boot) before any decorated route is served.
"""

import logging
from functools import wraps

from firebase_admin import auth as fb_auth
from flask import g, jsonify, request

from config import Config

logger = logging.getLogger('visionai.auth')

#: RFC 6750 §2.1 credential prefix.
_BEARER_PREFIX = 'Bearer '


def _client_ip() -> str:
    """Best-effort client IP for audit logging.

    ProxyFix has already normalised ``remote_addr`` from X-Forwarded-For when
    the app runs behind a trusted reverse proxy.

    Args:
        None.

    Returns:
        The client IP address, or 'unknown' when unavailable.
    """
    return request.remote_addr or 'unknown'


def _unauthorized(reason: str):
    """Build the standard 401 JSON envelope.

    Args:
        reason: Client-safe explanation (never contains internals or the token).

    Returns:
        Tuple of (Flask JSON response, 401).
    """
    return jsonify({'success': False, 'error': reason}), 401


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """Extract the credential from an RFC 6750 Authorization header.

    Args:
        authorization_header: Raw header value, or None when absent.

    Returns:
        The token string, or None when the header is missing or malformed.
    """
    if not authorization_header:
        return None
    if not authorization_header.startswith(_BEARER_PREFIX):
        return None
    token = authorization_header[len(_BEARER_PREFIX):].strip()
    return token or None


def verify_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims.

    Args:
        id_token: The raw JWT presented by the client.

    Returns:
        Decoded claim dict containing at least ``uid``.

    Raises:
        fb_auth.ExpiredIdTokenError: The token's ``exp`` claim has passed.
        fb_auth.RevokedIdTokenError: The token was revoked (only detectable when
            ``Config.CHECK_TOKEN_REVOKED`` is enabled).
        fb_auth.InvalidIdTokenError: Signature, issuer or audience mismatch.
    """
    return fb_auth.verify_id_token(id_token, check_revoked=Config.CHECK_TOKEN_REVOKED)


def require_auth(view):
    """Flask route decorator enforcing a valid Firebase Bearer JWT.

    On success, populates the request context before calling the view:
      * ``g.uid`` — Firebase Auth UID (the only trustworthy user identifier).
      * ``g.email`` — verified email claim, or an empty string.
      * ``g.display_name`` — ``name`` claim, falling back to the email local part.
      * ``g.claims`` — the full decoded claim dict.
      * ``g.login_method`` — ``'google'`` when the token came from the Google
        OIDC provider, otherwise ``'email'``.

    Args:
        view: The Flask view function to protect.

    Returns:
        The wrapped view function.

    Raises:
        Nothing. Failures short-circuit with HTTP 401 and a JSON body of
        ``{"success": false, "error": "<reason>"}`` where reason is one of
        "Missing Authorization header", "Invalid token format", "Token expired",
        "Token revoked" or "Invalid token".
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get('Authorization')
        if not header:
            logger.warning("Auth failure (missing header) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Missing Authorization header')

        token = extract_bearer_token(header)
        if not token:
            logger.warning("Auth failure (malformed header) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Invalid token format')

        try:
            claims = verify_token(token)
        except fb_auth.ExpiredIdTokenError:
            logger.warning("Auth failure (expired) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Token expired')
        except fb_auth.RevokedIdTokenError:
            logger.warning("Auth failure (revoked) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Token revoked')
        except (fb_auth.InvalidIdTokenError, ValueError):
            logger.warning("Auth failure (invalid) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Invalid token')
        except Exception:  # noqa: BLE001 — never leak SDK internals to clients
            logger.exception("Auth failure (unexpected) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Invalid token')

        uid = claims.get('uid') or claims.get('user_id')
        if not uid:
            logger.warning("Auth failure (no uid claim) ip=%s path=%s", _client_ip(), request.path)
            return _unauthorized('Invalid token')

        email = (claims.get('email') or '').lower()
        provider = (claims.get('firebase') or {}).get('sign_in_provider', '')

        g.uid = uid
        g.email = email
        g.display_name = claims.get('name') or (email.split('@')[0] if email else 'User')
        g.login_method = 'google' if provider == 'google.com' else 'email'
        g.claims = claims
        g.is_admin = bool(claims.get('admin'))

        return view(*args, **kwargs)

    return wrapper


def require_admin(view):
    """Flask route decorator enforcing admin-level Firebase custom claims.

    Must be applied AFTER ``@require_auth`` (i.e. listed before it in the
    decorator stack) so that ``g.uid`` and ``g.is_admin`` are already set.

    Args:
        view: The Flask view function to protect.

    Returns:
        The wrapped view function.

    Raises:
        Nothing. Non-admin callers receive HTTP 403 with a JSON body of
        ``{"success": false, "error": "Admin access required"}``.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not getattr(g, 'is_admin', False):
            logger.warning(
                "Admin access denied uid=%s ip=%s path=%s",
                getattr(g, 'uid', '?'), _client_ip(), request.path,
            )
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        return view(*args, **kwargs)

    return wrapper
