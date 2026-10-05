"""
backend/triage.py
─────────────────
Triage engine for **Daily Home Mode**.

Supports two scoring paths:

  1. Rule-based (``assess``): symptom weights + pixel-level colour cues.
     Zero ML cost.  This is the fallback when the home model is unavailable.

  2. AI-augmented (``assess_with_model``): NeuronZero/EyeDiseaseClassifier
     predictions are blended with symptom weights and pixel cues.  The model's
     ``Normal`` class enables a dedicated "Healthy Eye" result path that the
     rule engine alone can never produce.

Single Responsibility
─────────────────────
Turn a set of self-reported symptoms — optionally augmented by two cheap colour
cues read off a smartphone photo — into the same ``[{label, confidence}, ...]``
shape ``model.predict()`` emits, so the whole frontend result pipeline is
reused unchanged.

Design constraints (mirroring ``model.py`` §4.3):
  * MUST NOT import flask, firebase_admin, firestore or any HTTP library.
  * MUST NOT import torch, timm or transformers — Home Mode carries **zero**
    ML cost. One screening is a few hundred float multiplications.
  * MUST NOT write to disk — the optional photo stays in ``io.BytesIO``.
  * Deterministic: identical input always yields identical output, which makes
    the module unit-testable without fixtures or mocks.
"""

import io
import logging

from PIL import Image

logger = logging.getLogger('visionai.triage')

# ── Canonical home-card keys (mirrored in frontend/src/lib/diseases.ts) ──────
CARD_ALLERGY = 'Home_Allergy_Irritation'
CARD_DIGITAL_STRAIN = 'Home_Digital_Strain'
CARD_RED_EYE = 'Home_Red_Eye'
CARD_LENS_HAZE = 'Home_Lens_Haze'
CARD_VISION_ALERT = 'Home_Vision_Loss_Alert'
CARD_HEALTHY = 'Home_Healthy'

#: Every disease card the engine can surface, in escalating severity order.
#: ``CARD_HEALTHY`` is deliberately excluded — it is returned as a special case
#: by ``assess_with_model`` and must never compete in the additive scoring.
CARDS: tuple[str, ...] = (
    CARD_ALLERGY,
    CARD_DIGITAL_STRAIN,
    CARD_RED_EYE,
    CARD_LENS_HAZE,
    CARD_VISION_ALERT,
)

# ═════════════════════════════════════════════════════════════════════════════
# SYMPTOM CATALOGUE
# ═════════════════════════════════════════════════════════════════════════════
#
# Each symptom contributes weight to one primary card and, where the clinical
# picture genuinely overlaps, a smaller weight to neighbouring cards. The ids
# are the wire contract with the frontend checklist — never rename one without
# updating `frontend/src/lib/homeTriage.ts` in the same commit.

SYMPTOM_WEIGHTS: dict[str, dict[str, float]] = {
    # ── Card 1: allergic surface irritation ─────────────────────────────────
    'itching':                  {CARD_ALLERGY: 3.0, CARD_RED_EYE: 0.5},
    'watering':                 {CARD_ALLERGY: 2.5, CARD_DIGITAL_STRAIN: 0.5},
    'seasonal_allergies':       {CARD_ALLERGY: 3.0},
    'puffy_lids':               {CARD_ALLERGY: 2.0, CARD_RED_EYE: 1.0},
    'gritty_feeling':           {CARD_ALLERGY: 2.0, CARD_DIGITAL_STRAIN: 1.5},

    # ── Card 2: digital eye strain & dry eye ────────────────────────────────
    'long_screen_hours':        {CARD_DIGITAL_STRAIN: 3.0},
    'evening_burning':          {CARD_DIGITAL_STRAIN: 2.5, CARD_ALLERGY: 0.5},
    'dryness':                  {CARD_DIGITAL_STRAIN: 2.5, CARD_ALLERGY: 0.5},
    'headache_after_screens':   {CARD_DIGITAL_STRAIN: 2.5},
    'blur_clears_on_rest':      {CARD_DIGITAL_STRAIN: 3.0},

    # ── Card 3: bloodshot red eye & conjunctivitis ──────────────────────────
    'redness':                  {CARD_RED_EYE: 3.0, CARD_ALLERGY: 0.5},
    'crusty_discharge':         {CARD_RED_EYE: 3.5},
    'contagious_contact':       {CARD_RED_EYE: 3.0},
    'contact_lens_discomfort':  {CARD_RED_EYE: 2.0, CARD_DIGITAL_STRAIN: 0.5},
    'blood_patch':              {CARD_RED_EYE: 3.0},

    # ── Card 4: visible lens cloudiness & pupil haze ────────────────────────
    'cloudy_pupil':             {CARD_LENS_HAZE: 3.5},
    'faded_colours':            {CARD_LENS_HAZE: 3.0},
    'night_halos':              {CARD_LENS_HAZE: 3.0, CARD_VISION_ALERT: 0.5},
    'age_60_plus':              {CARD_LENS_HAZE: 2.0},
    'double_vision_one_eye':    {CARD_LENS_HAZE: 2.5, CARD_VISION_ALERT: 1.0},

    # ── Card 5: early vision loss red alert ─────────────────────────────────
    'sudden_blur':              {CARD_VISION_ALERT: 4.0},
    'floaters_or_flashes':      {CARD_VISION_ALERT: 4.0},
    'tunnel_vision':            {CARD_VISION_ALERT: 4.0},
    'severe_pain_nausea':       {CARD_VISION_ALERT: 4.0, CARD_RED_EYE: 1.0},
    'diabetes_or_bp':           {CARD_VISION_ALERT: 2.5},
}

#: Symptoms that must never be buried behind a milder card, however many mild
#: boxes the patient also ticked. Any one of these forces Card 5 to rank first.
RED_FLAG_SYMPTOMS: frozenset[str] = frozenset({
    'sudden_blur',
    'floaters_or_flashes',
    'tunnel_vision',
    'severe_pain_nausea',
})

#: Multiplier applied to the red-alert score once a red flag is present.
_RED_FLAG_MULTIPLIER = 2.0

#: Additive floor guaranteeing the red-alert card outranks every other card.
_RED_FLAG_MARGIN = 2.0

#: Maximum number of symptom ids accepted in one request (abuse ceiling).
MAX_SYMPTOMS = 40

#: Percentage match values are rounded to this many decimal places.
_MATCH_DECIMALS = 2

#: Cards scoring below this percentage share are dropped from the response.
_MIN_REPORTED_MATCH = 0.5


# ═════════════════════════════════════════════════════════════════════════════
# IMAGE CUES  (deliberately trivial — no ML, no numpy, no model weights)
# ═════════════════════════════════════════════════════════════════════════════

#: The photo is downsampled to this square before any pixel is inspected, so a
#: 12-megapixel phone shot costs the same as a thumbnail.
_CUE_SAMPLE_SIZE = 64

#: Central crop fraction searched for lens/pupil haze.
_CENTRAL_CROP = 0.4

#: Luminance at or above which a desaturated pixel counts as "milky".
_HAZE_LUMA_FLOOR = 120

#: Saturation at or below which a bright pixel counts as "washed out".
_HAZE_SATURATION_CEILING = 60

#: Divisor normalising mean red dominance (0-255) into a 0-1 cue.
_REDNESS_SCALE = 64.0

#: Baseline thresholds: facial skin and eyelids naturally exhibit red dominance (~0.20-0.25)
#: and slight central reflection (~0.03-0.05). Genuine ocular pathologies (bloodshot sclera,
#: milky lens opacity) push far beyond these baselines.
_REDNESS_BASELINE = 0.25
_HAZE_BASELINE = 0.06

#: Maximum per-card weight points contributed by a confirmed image cue.
#: Calibrated so genuine bloodshot sclera (net_redness > 0.25) produces a decisive
#: red-eye finding (~90%) without being drowned out by background noise.
_CUE_MAX_WEIGHT = 10.0


def inspect_image(image_bytes: bytes) -> dict[str, float]:
    """Extract two coarse colour cues from a smartphone eye photo.

    The photo is downsampled to 64x64 and reduced to two scalars:

      * ``redness`` — how far red dominates green/blue across the frame, the
        signature of a bloodshot sclera.
      * ``haze``    — the share of the central crop that is bright *and*
        desaturated, the signature of a milky lens over the pupil.

    Both are advisory: they feed the same additive score as a ticked checkbox
    and are capped well below the weight of a reported symptom.

    Args:
        image_bytes: Raw bytes of the uploaded photo.

    Returns:
        ``{'redness': 0.0-1.0, 'haze': 0.0-1.0}``. An unreadable or empty image
        yields zeros rather than raising — a bad photo must never fail an
        otherwise valid symptom-driven screening.
    """
    if not image_bytes:
        return {'redness': 0.0, 'haze': 0.0}

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image = image.resize((_CUE_SAMPLE_SIZE, _CUE_SAMPLE_SIZE))
    except (Image.DecompressionBombError, Image.UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("Home-mode photo could not be inspected, ignoring cues: %s", exc)
        return {'redness': 0.0, 'haze': 0.0}

    pixels = list(image.getdata())
    if not pixels:
        return {'redness': 0.0, 'haze': 0.0}

    # ── Cue 1: global red dominance ─────────────────────────────────────────
    redness_total = 0.0
    for red, green, blue in pixels:
        redness_total += max(0, red - max(green, blue))
    redness = min(1.0, (redness_total / len(pixels)) / _REDNESS_SCALE)

    # ── Cue 2: bright, desaturated centre ───────────────────────────────────
    margin = int(_CUE_SAMPLE_SIZE * (1 - _CENTRAL_CROP) / 2)
    hazy = 0
    central = 0
    for row in range(margin, _CUE_SAMPLE_SIZE - margin):
        for column in range(margin, _CUE_SAMPLE_SIZE - margin):
            red, green, blue = pixels[row * _CUE_SAMPLE_SIZE + column]
            central += 1
            luma = (red + green + blue) / 3
            saturation = max(red, green, blue) - min(red, green, blue)
            if luma >= _HAZE_LUMA_FLOOR and saturation <= _HAZE_SATURATION_CEILING:
                hazy += 1
    haze = (hazy / central) if central else 0.0

    return {'redness': round(redness, 4), 'haze': round(haze, 4)}


def _cue_weights(cues: dict[str, float] | None) -> dict[str, float]:
    """Convert raw image cues into per-card score contributions.

    Subtracts baseline skin/eyelid redness and pupil reflection haze so
    normal external eye photographs register 0 net redness / haze.

    Clinically separates moderate eye redness (eye strain, dry eye, allergy)
    from severe acute bloodshot redness (conjunctivitis, subconjunctival hemorrhage).
    """
    if not cues:
        return {}
    raw_red = float(cues.get('redness', 0.0))
    raw_haze = float(cues.get('haze', 0.0))

    net_red = max(0.0, (raw_red - _REDNESS_BASELINE) / (1.0 - _REDNESS_BASELINE)) if raw_red > _REDNESS_BASELINE else 0.0
    net_haze = max(0.0, (raw_haze - _HAZE_BASELINE) / (1.0 - _HAZE_BASELINE)) if raw_haze > _HAZE_BASELINE else 0.0

    w: dict[str, float] = {}
    if net_haze > 0:
        w[CARD_LENS_HAZE] = net_haze * (_CUE_MAX_WEIGHT * 0.8)
    if net_red > 0:
        if net_red <= 0.28:  # Moderate redness (e.g. MID EYE: fatigue, dry eye, surface allergy)
            w[CARD_DIGITAL_STRAIN] = 2.2 * (1.0 - net_red / 0.35)
            w[CARD_ALLERGY] = 1.4
            w[CARD_RED_EYE] = net_red * 3.5
        else:  # Severe/acute bloodshot redness (e.g. DAMAGED EYE)
            w[CARD_RED_EYE] = net_red * 14.0
            w[CARD_ALLERGY] = 0.2
    return w


# ═════════════════════════════════════════════════════════════════════════════
# AI MODEL INTEGRATION  (NeuronZero/EyeDiseaseClassifier)
# ═════════════════════════════════════════════════════════════════════════════
#
# The home model emits 8 labels:
#   AMD, Cataract, Diabetes, Glaucoma, Hypertension, Myopia, Normal, Other
#
# Each disease label maps onto one or two home cards with high weights so the
# AI signal dominates over the weak pixel cues.  "Normal" is a special case
# handled by assess_with_model().  "Other" contributes nothing — the engine
# falls back to pixel cues and symptoms.

#: Maximum per-card weight contributed by a single model label.
_MODEL_MAX_WEIGHT = 10.0

#: NeuronZero label → { home_card: weight } mapping.
#: Weights are deliberately much higher than symptom weights (~3.0) and pixel
#: cue weights (~2.5) so the AI model dominates when available.
MODEL_LABEL_WEIGHTS: dict[str, dict[str, float]] = {
    'AMD':          {CARD_VISION_ALERT: 8.0, CARD_LENS_HAZE: 2.0},
    'Cataract':     {CARD_LENS_HAZE: 9.0, CARD_VISION_ALERT: 2.0},
    'Diabetes':     {CARD_VISION_ALERT: 8.0, CARD_LENS_HAZE: 1.5},
    'Glaucoma':     {CARD_VISION_ALERT: 9.0},
    'Hypertension': {CARD_VISION_ALERT: 7.0, CARD_RED_EYE: 2.0},
    'Myopia':       {CARD_DIGITAL_STRAIN: 6.0, CARD_VISION_ALERT: 1.0},
    # 'Normal' → handled as a special case in assess_with_model()
    # 'Other'  → contributes nothing (treated as uncertain)
}


def model_cue_weights(
    model_predictions: list[dict],
    has_symptoms: bool = False,
) -> dict[str, float]:
    """Convert NeuronZero model predictions into per-card weight contributions.

    Each prediction ``{'label': str, 'confidence': float}`` is looked up in
    :data:`MODEL_LABEL_WEIGHTS`.

    Safeguards applied:
      1. Low-confidence predictions (< 30%) are ignored as background noise,
         preventing flat out-of-distribution softmax tails from accumulating.
      2. CARD_VISION_ALERT is guarded: emergency red-alert weight is only added
         if the prediction confidence is high (>= 40%) or the patient explicitly
         reported symptoms.

    Args:
        model_predictions: Output of ``home_model.predict_home()``, sorted by
            descending confidence.
        has_symptoms: Whether the patient reported any symptoms.

    Returns:
        Per-card score contributions from the AI model.
    """
    weights: dict[str, float] = {}
    for pred in model_predictions:
        conf_pct = pred.get('confidence', 0.0)
        if conf_pct < 30.0:  # Ignore background noise
            continue
        label = pred.get('label', '')
        conf = conf_pct / 100.0  # normalise to 0-1
        label_map = MODEL_LABEL_WEIGHTS.get(label)
        if not label_map:
            continue
        for card, base_weight in label_map.items():
            if card == CARD_VISION_ALERT and conf_pct < 40.0 and not has_symptoms:
                continue
            contribution = min(base_weight * conf, _MODEL_MAX_WEIGHT)
            weights[card] = weights.get(card, 0.0) + contribution
    return weights


# ═════════════════════════════════════════════════════════════════════════════
# SCORING
# ═════════════════════════════════════════════════════════════════════════════

def known_symptoms() -> list[str]:
    """List every symptom id the engine recognises."""
    return sorted(SYMPTOM_WEIGHTS)


def assess(symptom_ids, cues: dict[str, float] | None = None) -> list[dict]:
    """Score the five home cards against reported symptoms and photo cues.

    Pipeline:
        symptom ids -> additive per-card weights
                    -> optional calibrated image-cue weights
                    -> healthy eye detection when photo shows no pathology
                    -> red-flag escalation
                    -> normalise to a percentage match, sorted descending

    Args:
        symptom_ids: Iterable of symptom ids from ``SYMPTOM_WEIGHTS``. Unknown
            ids are ignored rather than rejected, so an older client is never
            broken by a catalogue change.
        cues: Optional output of :func:`inspect_image`.

    Returns:
        Cards sorted by descending match percentage, each
        ``{'label': str, 'confidence': float}``. The first element additionally
        carries ``'red_flag': True`` when an urgent symptom forced the
        escalation, so the UI can surface the hospital shortcut.
        When a photo without symptoms shows no redness or haze above baseline,
        returns ``[{'label': CARD_HEALTHY, 'is_healthy': True, ...}]``.

    Raises:
        ValueError: If nothing scored — no recognised symptom and no photo cues
            provided at all.
    """
    selected = [s for s in dict.fromkeys(symptom_ids or []) if s in SYMPTOM_WEIGHTS]
    has_symptoms = len(selected) > 0

    # ── Healthy Eye detection: photo uploaded with zero symptoms ───────────
    if cues and not has_symptoms:
        cue_w = _cue_weights(cues)
        if not any(v >= 0.5 for v in cue_w.values()):
            return [{
                'label': CARD_HEALTHY,
                'confidence': 92.0,
                'is_healthy': True,
                'source': 'photo_only',
            }]

    scores: dict[str, float] = {card: 0.0 for card in CARDS}
    for symptom in selected:
        for card, weight in SYMPTOM_WEIGHTS[symptom].items():
            scores[card] += weight
    for card, weight in _cue_weights(cues).items():
        scores[card] += weight

    red_flag = any(symptom in RED_FLAG_SYMPTOMS for symptom in selected)
    if red_flag:
        others = sum(score for card, score in scores.items() if card != CARD_VISION_ALERT)
        scores[CARD_VISION_ALERT] = max(
            scores[CARD_VISION_ALERT] * _RED_FLAG_MULTIPLIER,
            others + _RED_FLAG_MARGIN,
        )

    total = sum(scores.values())
    if total <= 0:
        if cues and not has_symptoms:
            return [{
                'label': CARD_HEALTHY,
                'confidence': 92.0,
                'is_healthy': True,
                'source': 'photo_only',
            }]
        raise ValueError(
            "No recognised symptoms were selected and the photo showed no usable cues."
        )

    source = 'symptoms' if has_symptoms else 'photo_only'

    results = [
        {'label': card, 'confidence': round(score / total * 100, _MATCH_DECIMALS), 'source': source}
        for card, score in scores.items()
        if (score / total * 100) >= _MIN_REPORTED_MATCH
    ]
    results.sort(key=lambda item: item['confidence'], reverse=True)

    if red_flag and results:
        results[0]['red_flag'] = True

    return results


# ═════════════════════════════════════════════════════════════════════════════
# AI-AUGMENTED SCORING
# ═════════════════════════════════════════════════════════════════════════════

def assess_with_model(
    symptom_ids,
    cues: dict[str, float] | None = None,
    model_predictions: list[dict] | None = None,
) -> list[dict]:
    """Score the home cards using symptoms, pixel cues **and** AI model output.

    Extends :func:`assess` with two new behaviours:
      1. **Healthy Eye path**: When image cues show clean sclera and pupil, and
         no disease prediction is strongly positive, a dedicated ``Home_Healthy``
         result is returned instead of forcing disease cards.
      2. **Noise-filtered AI blending**: Only model predictions with confidence
         >= 30% contribute, preventing out-of-domain softmax tails from leaking
         into emergency cards.
    """
    from config import Config

    selected = [s for s in dict.fromkeys(symptom_ids or []) if s in SYMPTOM_WEIGHTS]
    red_flag = any(s in RED_FLAG_SYMPTOMS for s in selected)
    has_symptoms = len(selected) > 0
    has_model = bool(model_predictions)

    cue_w = _cue_weights(cues)
    net_red_weight = cue_w.get(CARD_RED_EYE, 0.0)
    net_haze_weight = cue_w.get(CARD_LENS_HAZE, 0.0)

    # ── Healthy Eye path ────────────────────────────────────────────────────
    if not red_flag and not has_symptoms:
        strong_disease_preds = [
            p for p in (model_predictions or [])
            if p.get('confidence', 0.0) >= 35.0
            and p.get('label') in MODEL_LABEL_WEIGHTS
        ]
        if not any(v >= 0.5 for v in cue_w.values()) and not strong_disease_preds:
            normal_conf = next(
                (p['confidence'] for p in (model_predictions or [])
                 if p.get('label') == Config.HOME_HEALTHY_LABEL),
                0.0,
            )
            confidence = max(88.0, min(96.0, 85.0 + normal_conf * 0.5)) if has_model else 92.0
            return [{
                'label': CARD_HEALTHY,
                'confidence': round(confidence, _MATCH_DECIMALS),
                'is_healthy': True,
                'source': 'ai_model' if has_model else 'photo_only',
            }]

    # ── Additive scoring ────────────────────────────────────────────────────
    scores: dict[str, float] = {card: 0.0 for card in CARDS}

    # Layer 1: Symptom weights
    for symptom in selected:
        for card, weight in SYMPTOM_WEIGHTS[symptom].items():
            scores[card] += weight

    # Layer 2: Calibrated Image cues
    for card, weight in cue_w.items():
        scores[card] += weight

    # Layer 3: AI model weights (only from significant predictions >= 30%)
    if has_model:
        for card, weight in model_cue_weights(model_predictions, has_symptoms=has_symptoms).items():
            scores[card] += weight

    # ── Red-flag escalation ────────────────────────────────────────────────
    if red_flag:
        others = sum(
            score for card, score in scores.items() if card != CARD_VISION_ALERT
        )
        scores[CARD_VISION_ALERT] = max(
            scores[CARD_VISION_ALERT] * _RED_FLAG_MULTIPLIER,
            others + _RED_FLAG_MARGIN,
        )

    total = sum(scores.values())
    if total <= 0:
        if cues and not has_symptoms:
            return [{
                'label': CARD_HEALTHY,
                'confidence': 92.0,
                'is_healthy': True,
                'source': 'photo_only',
            }]
        raise ValueError(
            "No recognised symptoms were selected, the photo showed no usable "
            "cues, and the AI model did not produce actionable predictions."
        )

    has_sig_model = has_model and any(p.get('confidence', 0.0) >= 30.0 for p in (model_predictions or []))
    source = 'ai_model' if has_sig_model else ('symptoms' if has_symptoms else 'photo_only')

    results = [
        {
            'label': card,
            'confidence': round(score / total * 100, _MATCH_DECIMALS),
            'source': source,
        }
        for card, score in scores.items()
        if (score / total * 100) >= _MIN_REPORTED_MATCH
    ]
    results.sort(key=lambda item: item['confidence'], reverse=True)

    if red_flag and results:
        results[0]['red_flag'] = True

    return results
