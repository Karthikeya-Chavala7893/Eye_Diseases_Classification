"""
backend/tests/test_triage.py
────────────────────────────
Unit tests for the Daily Home Mode rule engine and integration tests for the
``mode=home`` branch of POST /api/predict.

The engine is pure and deterministic, so most of these need no fixtures at all.
"""

import io
import json
import os
import re

import pytest
from PIL import Image

import triage
from tests.static_analysis import imported_modules

PREDICT_URL = '/api/predict'

#: Repository root, from which the frontend mirror files are located.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOME_TRIAGE_TS = os.path.join(_REPO_ROOT, 'frontend', 'src', 'lib', 'homeTriage.ts')
DISEASES_TS = os.path.join(_REPO_ROOT, 'frontend', 'src', 'lib', 'diseases.ts')


def _solid_png(colour: tuple[int, int, int], size: int = 96) -> bytes:
    """Encode a single-colour PNG, used to exercise the image cues."""
    buffer = io.BytesIO()
    Image.new('RGB', (size, size), colour).save(buffer, format='PNG')
    return buffer.getvalue()


def _home_form(symptoms: list[str], image: bytes | None = None) -> dict:
    """Build a Home Mode multipart body for the Flask test client."""
    data: dict = {'mode': 'home', 'symptoms': json.dumps(symptoms)}
    if image is not None:
        data['image'] = (io.BytesIO(image), 'eye.png', 'image/png')
    return data


# ═════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE CONSTRAINTS
# ═════════════════════════════════════════════════════════════════════════════

class TestTriageIsolation:
    """triage.py must stay free of both the web layer and the ML stack."""

    @pytest.mark.parametrize('forbidden', [
        'flask', 'firebase_admin', 'firestore', 'requests', 'httpx',
        'torch', 'timm', 'transformers', 'torchvision',
    ])
    def test_triage_does_not_import(self, forbidden):
        assert forbidden not in imported_modules(triage.__file__)


# ═════════════════════════════════════════════════════════════════════════════
# CATALOGUE INTEGRITY
# ═════════════════════════════════════════════════════════════════════════════

class TestSymptomCatalogue:
    """Every weight must point at a real card, and every card must be reachable."""

    def test_every_weight_targets_a_known_card(self):
        for symptom, weights in triage.SYMPTOM_WEIGHTS.items():
            for card in weights:
                assert card in triage.CARDS, f'{symptom} targets unknown card {card}'

    def test_every_card_is_reachable(self):
        targeted = {card for w in triage.SYMPTOM_WEIGHTS.values() for card in w}
        assert targeted == set(triage.CARDS)

    def test_red_flags_are_real_symptoms(self):
        assert triage.RED_FLAG_SYMPTOMS <= set(triage.SYMPTOM_WEIGHTS)

    def test_known_symptoms_is_sorted_and_complete(self):
        assert triage.known_symptoms() == sorted(triage.SYMPTOM_WEIGHTS)


class TestFrontendContract:
    """The symptom ids and card keys are shared across the language boundary.

    A mismatch fails silently at runtime — the backend discards ids it does not
    recognise, and the UI falls back to a generic card — so it is caught here
    instead. Skipped when the frontend is not checked out alongside the backend.
    """

    @staticmethod
    def _read(path: str) -> str:
        if not os.path.isfile(path):
            pytest.skip(f'frontend source not available at {path}')
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    def test_symptom_ids_match_the_frontend_checklist(self):
        source = self._read(HOME_TRIAGE_TS)
        # Anchored on `icon:` so the group headers, which share the `id:` key
        # but carry a `title:` instead, are not mistaken for options.
        frontend_ids = set(re.findall(r"\{\s*id:\s*'([a-z0-9_]+)',\s*icon:", source))
        assert frontend_ids == set(triage.SYMPTOM_WEIGHTS)

    def test_red_flags_match_the_frontend_checklist(self):
        source = self._read(HOME_TRIAGE_TS)
        frontend_flags = {
            match.group(1)
            for match in re.finditer(
                r"\{\s*id:\s*'([a-z0-9_]+)',\s*icon:[^}]*redFlag:\s*true", source
            )
        }
        assert frontend_flags == set(triage.RED_FLAG_SYMPTOMS)

    def test_every_card_has_a_frontend_knowledge_base_entry(self):
        source = self._read(DISEASES_TS)
        home_keys = set(re.findall(r'^\s{4}(Home_[A-Za-z_]+):\s*\{', source, re.MULTILINE))
        # Home_Healthy is in HOME_DB but deliberately excluded from CARDS
        # (it's a special-case result from assess_with_model, not a disease card).
        expected = set(triage.CARDS) | {triage.CARD_HEALTHY}
        assert home_keys == expected


# ═════════════════════════════════════════════════════════════════════════════
# SCORING
# ═════════════════════════════════════════════════════════════════════════════

class TestAssess:
    """The five home cards, scored from symptoms alone."""

    @pytest.mark.parametrize('symptoms,expected', [
        (['itching', 'seasonal_allergies'], triage.CARD_ALLERGY),
        (['long_screen_hours', 'blur_clears_on_rest'], triage.CARD_DIGITAL_STRAIN),
        (['crusty_discharge', 'contagious_contact'], triage.CARD_RED_EYE),
        (['cloudy_pupil', 'faded_colours', 'night_halos'], triage.CARD_LENS_HAZE),
        (['sudden_blur', 'diabetes_or_bp'], triage.CARD_VISION_ALERT),
    ])
    def test_symptom_cluster_selects_its_card(self, symptoms, expected):
        assert triage.assess(symptoms)[0]['label'] == expected

    def test_matches_are_a_percentage_distribution(self):
        results = triage.assess(['itching', 'dryness', 'redness'])
        assert sum(item['confidence'] for item in results) == pytest.approx(100, abs=1.0)
        assert all(0 <= item['confidence'] <= 100 for item in results)

    def test_results_are_sorted_descending(self):
        results = triage.assess(['itching', 'watering', 'long_screen_hours'])
        scores = [item['confidence'] for item in results]
        assert scores == sorted(scores, reverse=True)

    def test_engine_is_deterministic(self):
        symptoms = ['redness', 'dryness', 'age_60_plus']
        assert triage.assess(symptoms) == triage.assess(symptoms)

    def test_unknown_symptom_ids_are_ignored(self):
        assert triage.assess(['itching', 'not_a_real_symptom']) == triage.assess(['itching'])

    def test_duplicate_symptoms_are_counted_once(self):
        assert triage.assess(['itching', 'itching']) == triage.assess(['itching'])

    def test_nothing_scoreable_raises(self):
        with pytest.raises(ValueError):
            triage.assess([])

    def test_only_unknown_symptoms_raises(self):
        with pytest.raises(ValueError):
            triage.assess(['nope', 'still_nope'])


class TestRedFlagEscalation:
    """An urgent symptom must never be buried behind a pile of mild ones."""

    @pytest.mark.parametrize('red_flag', sorted(triage.RED_FLAG_SYMPTOMS))
    def test_red_flag_outranks_a_pile_of_mild_symptoms(self, red_flag):
        mild = ['itching', 'watering', 'seasonal_allergies', 'puffy_lids',
                'gritty_feeling', 'long_screen_hours', 'dryness']
        results = triage.assess(mild + [red_flag])
        assert results[0]['label'] == triage.CARD_VISION_ALERT
        assert results[0]['red_flag'] is True

    def test_no_red_flag_leaves_the_marker_off(self):
        results = triage.assess(['itching', 'watering'])
        assert all('red_flag' not in item for item in results)

    def test_diabetes_alone_does_not_escalate(self):
        """A risk factor is not an emergency — it must not raise the red flag."""
        results = triage.assess(['diabetes_or_bp'])
        assert all('red_flag' not in item for item in results)


# ═════════════════════════════════════════════════════════════════════════════
# IMAGE CUES
# ═════════════════════════════════════════════════════════════════════════════

class TestInspectImage:
    """Two coarse colour cues, no ML."""

    def test_empty_bytes_yield_zero_cues(self):
        assert triage.inspect_image(b'') == {'redness': 0.0, 'haze': 0.0}

    def test_undecodable_bytes_yield_zero_cues(self):
        assert triage.inspect_image(b'not-an-image') == {'redness': 0.0, 'haze': 0.0}

    def test_red_frame_scores_high_redness(self):
        assert triage.inspect_image(_solid_png((220, 40, 40)))['redness'] > 0.5

    def test_neutral_frame_scores_low_redness(self):
        assert triage.inspect_image(_solid_png((90, 95, 100)))['redness'] < 0.1

    def test_milky_frame_scores_high_haze(self):
        assert triage.inspect_image(_solid_png((215, 215, 210)))['haze'] > 0.9

    def test_dark_frame_scores_no_haze(self):
        assert triage.inspect_image(_solid_png((20, 20, 20)))['haze'] == 0.0

    def test_cues_alone_can_produce_a_result(self):
        cues = triage.inspect_image(_solid_png((220, 40, 40)))
        assert triage.assess([], cues)[0]['label'] == triage.CARD_RED_EYE

    def test_cues_never_outvote_reported_symptoms(self):
        """A milky photo must not override an explicit red-flag report."""
        cues = triage.inspect_image(_solid_png((215, 215, 210)))
        assert triage.assess(['sudden_blur'], cues)[0]['label'] == triage.CARD_VISION_ALERT

    def test_clean_photo_without_symptoms_returns_healthy(self):
        """A clean photo with no symptoms returns Home_Healthy."""
        cues = triage.inspect_image(_solid_png((90, 95, 100)))
        res = triage.assess([], cues)
        assert len(res) == 1
        assert res[0]['label'] == triage.CARD_HEALTHY
        assert res[0]['is_healthy'] is True

    def test_damaged_red_photo_returns_high_confidence_red_eye(self):
        """A bloodshot photo alone scores Red Eye with >85% confidence."""
        cues = triage.inspect_image(_solid_png((220, 40, 40)))
        res = triage.assess([], cues)
        assert res[0]['label'] == triage.CARD_RED_EYE
        assert res[0]['confidence'] > 85.0

    def test_assess_with_model_flat_noise_returns_healthy(self):
        """Flat out-of-domain model predictions do not trigger Vision Alert."""
        cues = {'redness': 0.23, 'haze': 0.03}
        preds = [
            {'label': 'Other', 'confidence': 25.4},
            {'label': 'Cataract', 'confidence': 18.2},
            {'label': 'Glaucoma', 'confidence': 16.3},
            {'label': 'Normal', 'confidence': 16.1},
        ]
        res = triage.assess_with_model([], cues, preds)
        assert res[0]['label'] == triage.CARD_HEALTHY
        assert res[0]['is_healthy'] is True

    def test_moderate_and_damaged_cues_produce_distinct_results(self):
        """Moderate redness (mid eye) and acute redness (damaged eye) must not produce identical cards."""
        mid_cues = {'redness': 0.4269, 'haze': 0.0843}
        damaged_cues = {'redness': 0.4819, 'haze': 0.0947}
        mid_res = triage.assess([], mid_cues)
        damaged_res = triage.assess([], damaged_cues)
        # Mid eye top card should be strain or allergy irritation, NOT high-confidence acute red eye
        assert mid_res[0]['label'] != triage.CARD_VISION_ALERT
        assert mid_res[0]['label'] in (triage.CARD_ALLERGY, triage.CARD_DIGITAL_STRAIN)
        # Damaged eye top card should be acute bloodshot red eye
        assert damaged_res[0]['label'] == triage.CARD_RED_EYE
        assert damaged_res[0]['confidence'] > 85.0

    def test_assess_with_model_differentiates_mid_and_damaged_eyes(self):
        """With AI model, mid eye produces Digital Strain while damaged eye produces Red Eye."""
        mid_cues = {'redness': 0.4269, 'haze': 0.0843}
        mid_preds = [
            {'label': 'Myopia', 'confidence': 46.24},
            {'label': 'Other', 'confidence': 15.46},
            {'label': 'Normal', 'confidence': 13.00},
        ]
        damaged_cues = {'redness': 0.4819, 'haze': 0.0947}
        damaged_preds = [
            {'label': 'Other', 'confidence': 35.40},
            {'label': 'Cataract', 'confidence': 26.93},
            {'label': 'Normal', 'confidence': 12.76},
        ]
        mid_res = triage.assess_with_model([], mid_cues, mid_preds)
        damaged_res = triage.assess_with_model([], damaged_cues, damaged_preds)
        assert mid_res[0]['label'] == triage.CARD_DIGITAL_STRAIN
        assert damaged_res[0]['label'] == triage.CARD_RED_EYE
        assert damaged_res[0]['confidence'] > 85.0


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════

class TestHomeModeEndpoint:
    """POST /api/predict with mode=home."""

    def test_symptoms_only_screening_succeeds(self, authed_client):
        res = authed_client.post(PREDICT_URL, data=_home_form(['itching', 'seasonal_allergies']),
                                 content_type='multipart/form-data')
        assert res.status_code == 200
        body = res.get_json()['data']
        assert body['mode'] == 'home'
        assert body['model'] == 'rule-based-triage-v1'
        assert body['predictions'][0]['label'] == triage.CARD_ALLERGY

    def test_photo_is_inspected_and_cues_returned(self, authed_client):
        res = authed_client.post(
            PREDICT_URL,
            data=_home_form(['redness'], _solid_png((220, 40, 40))),
            content_type='multipart/form-data',
        )
        assert res.status_code == 200
        assert res.get_json()['data']['cues']['redness'] > 0.5

    def test_photo_only_screening_succeeds(self, authed_client):
        res = authed_client.post(
            PREDICT_URL,
            data=_home_form([], _solid_png((220, 40, 40))),
            content_type='multipart/form-data',
        )
        assert res.status_code == 200
        assert res.get_json()['data']['predictions'][0]['label'] == triage.CARD_RED_EYE

    def test_no_symptoms_and_no_photo_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL, data=_home_form([]),
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert 'at least one symptom' in res.get_json()['error']

    def test_malformed_symptoms_json_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL,
                                 data={'mode': 'home', 'symptoms': '{not json'},
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert 'JSON array' in res.get_json()['error']

    def test_non_string_symptoms_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL,
                                 data={'mode': 'home', 'symptoms': '[1, 2, 3]'},
                                 content_type='multipart/form-data')
        assert res.status_code == 400

    def test_unknown_mode_returns_400(self, authed_client):
        res = authed_client.post(PREDICT_URL, data={'mode': 'telepathy'},
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert 'Unknown mode' in res.get_json()['error']

    def test_home_mode_requires_authentication(self, client):
        res = client.post(PREDICT_URL, data=_home_form(['itching']),
                          content_type='multipart/form-data')
        assert res.status_code == 401

    def test_home_mode_works_while_the_ai_model_is_unloaded(
        self, client, mock_verify_token, mock_db, auth_headers
    ):
        """Home Mode must not depend on RETFound being warm."""
        res = client.post(PREDICT_URL, data=_home_form(['itching']),
                          content_type='multipart/form-data', headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()['data']['mode'] == 'home'

    def test_red_flag_reaches_the_client(self, authed_client):
        res = authed_client.post(PREDICT_URL, data=_home_form(['sudden_blur', 'itching']),
                                 content_type='multipart/form-data')
        top = res.get_json()['data']['predictions'][0]
        assert top['label'] == triage.CARD_VISION_ALERT
        assert top['red_flag'] is True

    def test_home_screening_is_persisted_under_the_rule_engine_id(self, authed_client, mock_db):
        authed_client.post(PREDICT_URL, data=_home_form(['itching']),
                           content_type='multipart/form-data')
        document = mock_db.collection.return_value.add.call_args[0][0]
        assert document['modelId'] == 'rule-based-triage-v1'


class TestClinicalModeUnchanged:
    """The clinical path must behave exactly as it did before mode routing."""

    def test_omitted_mode_defaults_to_clinical(self, authed_client, minimal_png):
        res = authed_client.post(
            PREDICT_URL,
            data={'image': (io.BytesIO(minimal_png), 'retina.png', 'image/png')},
            content_type='multipart/form-data',
        )
        assert res.status_code == 200
        assert res.get_json()['data']['mode'] == 'clinical'

    def test_explicit_clinical_mode_still_requires_an_image(self, authed_client):
        res = authed_client.post(PREDICT_URL, data={'mode': 'clinical'},
                                 content_type='multipart/form-data')
        assert res.status_code == 400
        assert res.get_json()['error'] == 'No image uploaded'
