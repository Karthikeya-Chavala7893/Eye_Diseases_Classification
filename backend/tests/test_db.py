"""
backend/tests/test_db.py
────────────────────────
Unit tests for the Firestore persistence layer (``backend/db.py``).

The Firestore client is a MagicMock, so these tests assert the exact document
shapes and query chains the module builds — including the privacy rules that
forbid persisting images or credentials.
"""

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from firebase_admin import firestore

import db as db_module
from config import Config
from tests.static_analysis import imported_modules


# ═════════════════════════════════════════════════════════════════════════════
# MODULE CONTRACT
# ═════════════════════════════════════════════════════════════════════════════

class TestModuleIsolation:
    """db.py must not depend on the web or inference layers (constraint #12)."""

    def test_db_module_does_not_import_flask_model_or_auth(self):
        imported = imported_modules(db_module.__file__)
        assert imported.isdisjoint({'flask', 'model', 'auth'}), (
            f'db.py imports forbidden modules: {sorted(imported & {"flask", "model", "auth"})}'
        )

    def test_uninitialised_client_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr(db_module, '_client', None)
        with pytest.raises(RuntimeError, match='not initialised'):
            db_module.get_user('any-uid')


# ═════════════════════════════════════════════════════════════════════════════
# upsert_user
# ═════════════════════════════════════════════════════════════════════════════

class TestUpsertUser:
    """User profiles merge, use server timestamps, and never carry secrets."""

    def test_upsert_user_new_document_returns_true_and_sets_created_at(self, mock_db):
        created = db_module.upsert_user('uid-1', 'A@Example.com', 'Alice', 'email')
        assert created is True

        doc_ref = mock_db.collection.return_value.document.return_value
        payload, kwargs = doc_ref.set.call_args[0][0], doc_ref.set.call_args[1]
        assert payload['uid'] == 'uid-1'
        assert payload['email'] == 'a@example.com'          # lowercased
        assert payload['displayName'] == 'Alice'
        assert payload['loginMethod'] == 'email'
        assert payload['createdAt'] is firestore.SERVER_TIMESTAMP
        assert payload['lastLogin'] is firestore.SERVER_TIMESTAMP
        assert kwargs == {'merge': True}                    # constraint: merge, never overwrite

    def test_upsert_user_existing_document_returns_false_and_preserves_created_at(self, mock_db):
        existing = mock_db.collection.return_value.document.return_value.get.return_value
        existing.exists = True
        existing.to_dict.return_value = {'uid': 'uid-1'}

        created = db_module.upsert_user('uid-1', 'a@example.com', 'Alice', 'email')
        assert created is False

        payload = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert 'createdAt' not in payload

    def test_upsert_user_never_writes_password_fields(self, mock_db):
        db_module.upsert_user('uid-1', 'a@example.com', 'Alice', 'email')
        payload = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert not any('password' in key.lower() for key in payload)

    def test_upsert_user_targets_the_users_collection(self, mock_db):
        db_module.upsert_user('uid-1', 'a@example.com', 'Alice', 'email')
        mock_db.collection.assert_called_with(Config.USERS_COLLECTION)

    def test_upsert_user_propagates_firestore_errors(self, mock_db):
        mock_db.collection.return_value.document.return_value.set.side_effect = Exception('boom')
        with pytest.raises(Exception, match='boom'):
            db_module.upsert_user('uid-1', 'a@example.com', 'Alice', 'email')


# ═════════════════════════════════════════════════════════════════════════════
# get_user
# ═════════════════════════════════════════════════════════════════════════════

class TestGetUser:
    """Reads normalise Firestore timestamps into ISO-8601 strings."""

    def test_get_user_missing_document_returns_none(self, mock_db):
        assert db_module.get_user('nobody') is None

    def test_get_user_existing_document_returns_iso_timestamps(self, mock_db):
        moment = datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc)
        snapshot = mock_db.collection.return_value.document.return_value.get.return_value
        snapshot.exists = True
        snapshot.to_dict.return_value = {
            'uid': 'uid-1', 'email': 'a@example.com', 'displayName': 'Alice',
            'createdAt': moment, 'lastLogin': moment,
        }

        user = db_module.get_user('uid-1')
        assert user['uid'] == 'uid-1'
        assert user['createdAt'] == moment.isoformat()
        assert user['lastLogin'] == moment.isoformat()

    def test_get_user_unresolved_timestamp_becomes_none(self, mock_db):
        snapshot = mock_db.collection.return_value.document.return_value.get.return_value
        snapshot.exists = True
        snapshot.to_dict.return_value = {'uid': 'uid-1', 'createdAt': None, 'lastLogin': None}

        user = db_module.get_user('uid-1')
        assert user['createdAt'] is None


# ═════════════════════════════════════════════════════════════════════════════
# save_scan
# ═════════════════════════════════════════════════════════════════════════════

class TestSaveScan:
    """Scans persist results and a hash — never the image itself."""

    PREDICTIONS = [
        {'label': 'Glaucoma', 'confidence': 88.12},
        {'label': 'Healthy_Retina', 'confidence': 11.88},
    ]

    def test_save_scan_returns_generated_document_id(self, mock_db):
        assert db_module.save_scan('uid-1', self.PREDICTIONS, b'imagebytes') == 'scan-doc-id'

    def test_save_scan_stores_sha256_hash_not_image_bytes(self, mock_db):
        image = b'\x89PNG-fake-payload'
        db_module.save_scan('uid-1', self.PREDICTIONS, image)

        document = mock_db.collection.return_value.add.call_args[0][0]
        assert document['imageHash'] == hashlib.sha256(image).hexdigest()
        assert image not in document.values()
        assert not any(isinstance(value, bytes) for value in document.values())

    def test_save_scan_records_top_prediction_and_server_timestamp(self, mock_db):
        db_module.save_scan('uid-1', self.PREDICTIONS, b'x')

        document = mock_db.collection.return_value.add.call_args[0][0]
        assert document['uid'] == 'uid-1'
        assert document['primaryLabel'] == 'Glaucoma'
        assert document['confidence'] == 88.12
        assert document['allResults'] == self.PREDICTIONS
        assert document['modelId'] == Config.LOCAL_MODEL_ID
        assert document['timestamp'] is firestore.SERVER_TIMESTAMP

    def test_save_scan_empty_predictions_raises_value_error(self, mock_db):
        with pytest.raises(ValueError, match='at least one entry'):
            db_module.save_scan('uid-1', [], b'x')


# ═════════════════════════════════════════════════════════════════════════════
# get_scan_history
# ═════════════════════════════════════════════════════════════════════════════

class TestGetScanHistory:
    """History queries are UID-scoped, ordered and hard-bounded."""

    def _limit_mock(self, mock_db):
        return mock_db.collection.return_value.where.return_value.order_by.return_value.limit

    @pytest.mark.parametrize('requested,expected', [
        (None, Config.SCAN_HISTORY_DEFAULT_LIMIT),
        (1, 1),
        (10, 10),
        (50, 50),
        (51, 50),
        (10_000, 50),
        (0, 1),
        (-5, 1),
        ('7', 7),
        ('abc', Config.SCAN_HISTORY_DEFAULT_LIMIT),
    ])
    def test_get_scan_history_clamps_limit(self, mock_db, requested, expected):
        if requested is None:
            db_module.get_scan_history('uid-1')
        else:
            db_module.get_scan_history('uid-1', requested)
        self._limit_mock(mock_db).assert_called_with(expected)

    def test_get_scan_history_filters_by_uid_with_field_filter(self, mock_db):
        """Uses the keyword FieldFilter API, not the deprecated positional form."""
        db_module.get_scan_history('uid-1')

        kwargs = mock_db.collection.return_value.where.call_args[1]
        assert mock_db.collection.return_value.where.call_args[0] == ()
        field_filter = kwargs['filter']
        assert isinstance(field_filter, firestore.FieldFilter)
        assert field_filter.field_path == 'uid'
        assert field_filter.value == 'uid-1'

    def test_get_scan_history_orders_by_timestamp_descending(self, mock_db):
        db_module.get_scan_history('uid-1')
        mock_db.collection.return_value.where.return_value.order_by.assert_called_with(
            'timestamp', direction=firestore.Query.DESCENDING
        )

    def test_get_scan_history_missing_index_raises_index_not_ready(self, mock_db):
        """A FAILED_PRECONDITION from Firestore becomes an actionable error."""
        from google.api_core import exceptions as gcloud_exceptions

        self._limit_mock(mock_db).return_value.get.side_effect = (
            gcloud_exceptions.FailedPrecondition('The query requires an index.')
        )
        with pytest.raises(db_module.IndexNotReadyError, match='index is not ready'):
            db_module.get_scan_history('uid-1')

    def test_get_scan_history_maps_documents_to_serialisable_dicts(self, mock_db):
        moment = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)
        snapshot = MagicMock()
        snapshot.id = 'scan-1'
        snapshot.to_dict.return_value = {
            'uid': 'uid-1', 'primaryLabel': 'Cataract', 'confidence': 71.5,
            'allResults': [{'label': 'Cataract', 'confidence': 71.5}],
            'modelId': Config.LOCAL_MODEL_ID, 'imageHash': 'a' * 64, 'timestamp': moment,
        }
        self._limit_mock(mock_db).return_value.get.return_value = [snapshot]

        scans = db_module.get_scan_history('uid-1')
        assert len(scans) == 1
        assert scans[0]['id'] == 'scan-1'
        assert scans[0]['primaryLabel'] == 'Cataract'
        assert scans[0]['timestamp'] == moment.isoformat()
