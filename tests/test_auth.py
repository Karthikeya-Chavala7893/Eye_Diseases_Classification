"""
tests/test_auth.py
──────────────────
Integration tests for authentication routes:
  - POST /auth/register
  - POST /auth/login
  - GET  /auth/logout

All Supabase calls are intercepted by the mock in conftest.py.
"""

import json
from unittest.mock import MagicMock

import pytest


# ═════════════════════════════════════════════════════════════════════════════
# REGISTRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestRegistration:
    """POST /auth/register"""

    def test_register_success(self, client, mock_supabase):
        """Valid new user registration returns HTTP 200 with success flag."""
        # No existing user
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[])
        mock_supabase.table.return_value.insert.return_value.execute.return_value = \
            MagicMock(data=[{'id': 'new-uuid'}])

        res = client.post('/auth/register',
                          json={'email': 'new@visionai.com', 'password': 'ValidPass1', 'name': 'New User'},
                          content_type='application/json')

        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert 'user' in data

    def test_register_duplicate_email(self, client, mock_supabase):
        """Registering with an already-existing email returns HTTP 400."""
        existing = {
            'id': 'existing-uuid', 'email': 'dupe@visionai.com', 'name': 'Existing',
            'phone': None, 'password_hash': 'hashed', 'login_method': 'Password',
            'role': 'user', 'is_active': True, 'last_login': None, 'created_at': '2026-01-01'
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[existing])

        res = client.post('/auth/register',
                          json={'email': 'dupe@visionai.com', 'password': 'ValidPass1', 'name': 'Dupe'},
                          content_type='application/json')

        assert res.status_code == 400
        data = res.get_json()
        assert data['success'] is False
        assert 'already registered' in data['error'].lower()

    def test_register_password_too_short(self, client, mock_supabase):
        """Password under 8 characters returns HTTP 400."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[])

        res = client.post('/auth/register',
                          json={'email': 'short@visionai.com', 'password': 'abc', 'name': 'Short'},
                          content_type='application/json')

        assert res.status_code == 400
        data = res.get_json()
        assert data['success'] is False
        assert '8' in data['error']

    def test_register_missing_fields(self, client):
        """Missing required fields (no name) returns HTTP 400."""
        res = client.post('/auth/register',
                          json={'email': 'noemail@visionai.com', 'password': 'ValidPass1'},
                          content_type='application/json')

        assert res.status_code == 400
        data = res.get_json()
        assert data['success'] is False

    def test_register_missing_email(self, client):
        """Missing email field returns HTTP 400."""
        res = client.post('/auth/register',
                          json={'password': 'ValidPass1', 'name': 'No Email'},
                          content_type='application/json')

        assert res.status_code == 400
        data = res.get_json()
        assert data['success'] is False


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLogin:
    """POST /auth/login"""

    def test_login_success(self, registered_user, client, mock_supabase):
        """Valid credentials return HTTP 200 with success flag and user info."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[registered_user['data']])

        res = client.post('/auth/login',
                          json={'email': registered_user['email'], 'password': registered_user['password']},
                          content_type='application/json')

        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['user']['email'] == registered_user['email']

    def test_login_wrong_password(self, registered_user, client, mock_supabase):
        """Wrong password returns HTTP 401."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[registered_user['data']])

        res = client.post('/auth/login',
                          json={'email': registered_user['email'], 'password': 'WrongPassword!'},
                          content_type='application/json')

        assert res.status_code == 401
        data = res.get_json()
        assert data['success'] is False

    def test_login_nonexistent_email(self, client, mock_supabase):
        """Login with an email not in database returns HTTP 401."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[])

        res = client.post('/auth/login',
                          json={'email': 'ghost@visionai.com', 'password': 'AnyPass123'},
                          content_type='application/json')

        assert res.status_code == 401
        data = res.get_json()
        assert data['success'] is False

    def test_login_empty_credentials(self, client):
        """Empty JSON body returns HTTP 401 (treated as invalid credentials)."""
        res = client.post('/auth/login',
                          json={},
                          content_type='application/json')

        assert res.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# LOGOUT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLogout:
    """GET /auth/logout"""

    def test_logout_requires_auth(self, client):
        """Unauthenticated logout request is rejected (no infinite redirect)."""
        res = client.get('/auth/logout', follow_redirects=False)
        # Either 302 redirect to login or 401 — either is acceptable
        assert res.status_code in (302, 401)

    def test_logout_authenticated_user(self, authenticated_client):
        """Authenticated user can log out and is redirected."""
        res = authenticated_client.get('/auth/logout', follow_redirects=False)
        assert res.status_code == 302
