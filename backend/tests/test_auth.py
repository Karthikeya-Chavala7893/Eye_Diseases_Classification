"""
backend/tests/test_auth.py
──────────────────────────
Unit and integration tests for the Firebase JWT verification layer
(``backend/auth.py``) and the two authenticated user endpoints it protects.

Firebase's ``verify_id_token`` is always patched — no Google public keys are
ever fetched.
"""

import pytest
from firebase_admin import auth as fb_auth
from flask import g

import auth as auth_module

SYNC_URL = '/api/user/sync'
SCANS_URL = '/api/user/scans'


# ═════════════════════════════════════════════════════════════════════════════
# HEADER PARSING (RFC 6750 §2.1)
# ═════════════════════════════════════════════════════════════════════════════

class TestBearerExtraction:
    """extract_bearer_token() accepts only well-formed Bearer credentials."""

    def test_extract_valid_bearer_header_returns_token(self):
        assert auth_module.extract_bearer_token('Bearer abc.def.ghi') == 'abc.def.ghi'

    @pytest.mark.parametrize('header', [
        None,
        '',
        'abc.def.ghi',          # no scheme
        'Token abc.def.ghi',    # wrong scheme
        'bearer abc.def.ghi',   # scheme is case-sensitive per RFC 6750
        'Bearer ',              # empty credential
        'Bearer    ',
    ])
    def test_extract_malformed_header_returns_none(self, header):
        assert auth_module.extract_bearer_token(header) is None


# ═════════════════════════════════════════════════════════════════════════════
# DECORATOR BEHAVIOUR
# ═════════════════════════════════════════════════════════════════════════════

class TestRequireAuthDecorator:
    """require_auth populates flask.g from verified claims, or returns 401."""

    def test_require_auth_valid_token_populates_request_context(
        self, application, mock_verify_token
    ):
        captured = {}

        @auth_module.require_auth
        def protected():
            captured.update(uid=g.uid, email=g.email,
                            name=g.display_name, method=g.login_method)
            return 'ok'

        with application.test_request_context(
            '/api/protected', headers={'Authorization': 'Bearer valid.token'}
        ):
            assert protected() == 'ok'

        assert captured == {
            'uid': 'test-uid-1234',
            'email': 'test@visionai.com',
            'name': 'Test User',
            'method': 'email',
        }

    def test_require_auth_google_provider_sets_google_login_method(
        self, application, mock_verify_token
    ):
        mock_verify_token.return_value = {
            'uid': 'google-uid', 'email': 'G@Example.com', 'name': 'G User',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        captured = {}

        @auth_module.require_auth
        def protected():
            captured.update(method=g.login_method, email=g.email)
            return 'ok'

        with application.test_request_context(
            '/api/protected', headers={'Authorization': 'Bearer valid.token'}
        ):
            protected()

        assert captured['method'] == 'google'
        assert captured['email'] == 'g@example.com'   # normalised to lowercase

    def test_require_auth_token_without_uid_claim_returns_401(
        self, application, mock_verify_token
    ):
        mock_verify_token.return_value = {'email': 'nobody@visionai.com'}

        @auth_module.require_auth
        def protected():
            return 'should not run'

        with application.test_request_context(
            '/api/protected', headers={'Authorization': 'Bearer valid.token'}
        ):
            response, status = protected()

        assert status == 401
        assert response.get_json()['error'] == 'Invalid token'

    def test_require_auth_missing_name_claim_falls_back_to_email_local_part(
        self, application, mock_verify_token
    ):
        mock_verify_token.return_value = {'uid': 'u1', 'email': 'jane.doe@visionai.com'}
        captured = {}

        @auth_module.require_auth
        def protected():
            captured['name'] = g.display_name
            return 'ok'

        with application.test_request_context(
            '/api/protected', headers={'Authorization': 'Bearer valid.token'}
        ):
            protected()

        assert captured['name'] == 'jane.doe'

    def test_require_auth_never_logs_the_token(self, application, mock_verify_token, caplog):
        mock_verify_token.side_effect = fb_auth.InvalidIdTokenError('nope')
        secret = 'super.secret.jwt.value'

        @auth_module.require_auth
        def protected():
            return 'ok'

        with application.test_request_context(
            '/api/protected', headers={'Authorization': f'Bearer {secret}'}
        ):
            with caplog.at_level('WARNING'):
                protected()

        assert secret not in caplog.text
        assert 'Auth failure' in caplog.text


# ═════════════════════════════════════════════════════════════════════════════
# POST /api/user/sync
# ═════════════════════════════════════════════════════════════════════════════

class TestUserSync:
    """Profile upsert derives every field from verified JWT claims."""

    def test_user_sync_first_call_creates_profile(self, authed_client, mock_db):
        res = authed_client.post(SYNC_URL, json={})
        assert res.status_code == 200
        body = res.get_json()
        assert body['success'] is True
        assert body['data'] == {'uid': 'test-uid-1234', 'created': True}

    def test_user_sync_existing_profile_reports_created_false(self, authed_client, mock_db):
        existing = mock_db.collection.return_value.document.return_value.get.return_value
        existing.exists = True
        existing.to_dict.return_value = {'uid': 'test-uid-1234'}

        res = authed_client.post(SYNC_URL, json={})
        assert res.status_code == 200
        assert res.get_json()['data']['created'] is False

    def test_user_sync_ignores_client_supplied_uid(self, authed_client, mock_db):
        """A caller cannot impersonate another user by posting a uid (constraint #6)."""
        res = authed_client.post(SYNC_URL, json={'uid': 'attacker-uid', 'role': 'admin'})
        assert res.status_code == 200
        assert res.get_json()['data']['uid'] == 'test-uid-1234'

        mock_db.collection.return_value.document.assert_called_with('test-uid-1234')
        written = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert written['uid'] == 'test-uid-1234'
        assert 'role' not in written

    def test_user_sync_never_persists_a_password(self, authed_client, mock_db):
        authed_client.post(SYNC_URL, json={'password': 'hunter2'})
        written = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert not any('password' in key.lower() for key in written)

    def test_user_sync_without_token_returns_401(self, client):
        res = client.post(SYNC_URL, json={})
        assert res.status_code == 401
        assert res.get_json()['error'] == 'Missing Authorization header'


# ═════════════════════════════════════════════════════════════════════════════
# GET /api/user/scans
# ═════════════════════════════════════════════════════════════════════════════

class TestUserScans:
    """Scan history is scoped to the authenticated UID and bounded in size."""

    def test_user_scans_without_token_returns_401(self, client):
        res = client.get(SCANS_URL)
        assert res.status_code == 401

    def test_user_scans_empty_history_returns_empty_list(self, authed_client, mock_db):
        res = authed_client.get(SCANS_URL)
        assert res.status_code == 200
        assert res.get_json()['data'] == {'scans': [], 'total': 0}

    def test_user_scans_queries_only_the_callers_uid(self, authed_client, mock_db):
        authed_client.get(SCANS_URL)
        field_filter = mock_db.collection.return_value.where.call_args[1]['filter']
        assert field_filter.field_path == 'uid'
        assert field_filter.value == 'test-uid-1234'

    def test_user_scans_missing_index_returns_actionable_503(self, authed_client, mock_db):
        """A missing composite index yields 503 with guidance, never a bare 500."""
        from google.api_core import exceptions as gcloud_exceptions

        (mock_db.collection.return_value.where.return_value
            .order_by.return_value.limit.return_value
            .get.side_effect) = gcloud_exceptions.FailedPrecondition('needs an index')

        res = authed_client.get(SCANS_URL)
        assert res.status_code == 503
        body = res.get_json()
        assert body['success'] is False
        assert 'firestore.indexes.json' in body['error']

    def test_user_scans_limit_is_clamped_to_maximum(self, authed_client, mock_db):
        authed_client.get(f'{SCANS_URL}?limit=9999')
        limit_call = (mock_db.collection.return_value
                      .where.return_value.order_by.return_value.limit)
        limit_call.assert_called_with(50)

    def test_user_scans_invalid_limit_falls_back_to_default(self, authed_client, mock_db):
        authed_client.get(f'{SCANS_URL}?limit=not-a-number')
        limit_call = (mock_db.collection.return_value
                      .where.return_value.order_by.return_value.limit)
        limit_call.assert_called_with(10)
