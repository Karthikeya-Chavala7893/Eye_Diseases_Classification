/**
 * types/prediction.ts
 * Inference result contracts and the disease knowledge-base schema.
 */

/**
 * Which arm of the dual-mode screening gateway produced a result.
 *
 *   `clinical` — RETFound inference over a fundus/OCT retinal scan.
 *   `home`     — rule-based triage over a symptom checklist plus an optional
 *                smartphone photo. No neural network is involved.
 */
export type ScreeningMode = 'clinical' | 'home';

/** One class score from the classifier, or one card match from home triage. */
export interface PredictionResult {
  /** Raw label emitted by the engine, e.g. "Healthy_Retina" or "Home_Red_Eye". */
  label: string;
  /** Confidence (clinical) or match strength (home) as a percentage, 0.00–100.00. */
  confidence: number;
  /** Set by home triage when an urgent symptom forced this card to the top. */
  red_flag?: boolean;
  /** Evidence source: 'ai_model' | 'symptoms' | 'photo_only'. Home mode only. */
  source?: 'ai_model' | 'symptoms' | 'photo_only';
  /** True when the model classified the eye as Normal (healthy). Home mode only. */
  is_healthy?: boolean;
  /** True when only pixel cues were used (no model, no symptoms). Confidence is capped. */
  low_evidence?: boolean;
}

/** Coarse colour cues read off a home-mode photo; both range 0–1. */
export interface ImageCues {
  /** How far red dominates green/blue — the bloodshot-sclera signal. */
  redness: number;
  /** Share of the central crop that is bright and desaturated — lens haze. */
  haze: number;
}

/** Payload of `POST /api/predict`. */
export interface PredictResponse {
  /** Sorted descending by confidence. */
  predictions: PredictionResult[];
  /** Which mode produced these results. */
  mode: ScreeningMode;
  model: string;
  inference: 'local';
  /** Display name of the authenticated patient, echoed from the verified JWT. */
  user: string;
  /** Present in home mode when a photo was supplied. */
  cues?: ImageCues;
  /** True when the NeuronZero model was used for home screening classification. */
  home_model_used?: boolean;
}

/** One entry in a user's persisted screening history. */
export interface ScanRecord {
  id: string;
  primaryLabel: string | null;
  confidence: number | null;
  allResults: PredictionResult[];
  modelId: string | null;
  imageHash: string | null;
  timestamp: string | null;
}

/** Payload of `GET /api/user/scans`. */
export interface ScanHistoryData {
  scans: ScanRecord[];
  total: number;
}

/** Visual and clinical urgency band driving colour and iconography. */
export type Severity = 'healthy' | 'warning' | 'danger';

/** An actionable clinical recommendation card. */
export interface Recommendation {
  icon: string;
  title: string;
  text: string;
  priority?: 'routine' | 'important' | 'urgent';
}

/** A lifestyle habit card with a suggested cadence. */
export interface Habit {
  icon: string;
  title: string;
  desc: string;
  freq: string;
}

/** A prevention tip card. */
export interface PreventionTip {
  icon: string;
  title: string;
  text: string;
}

/**
 * Optional badge overrides for entries whose urgency band does not map cleanly
 * onto the three clinical severities — the home cards, which carry five.
 */
export interface BadgeStyle {
  /** Text shown inside the pill, e.g. "Chronic Attention". */
  label: string;
  /** Foreground colour. */
  color: string;
  /** Pill background. */
  background: string;
}

/** A full knowledge-base entry for one detectable condition. */
export interface DiseaseEntry {
  /** Human-readable condition name. */
  name: string;
  severity: Severity;
  /** Which screening mode surfaces this entry; defaults to clinical. */
  mode?: ScreeningMode;
  /** Overrides the severity pill for the five-band home scale. */
  badge?: BadgeStyle;
  /** Home cards only: what this card covers, shown above the guidance tabs. */
  covers?: string;
  /** Emoji icon. */
  icon: string;
  /** Hex accent colour for the primary-result gradient. */
  color: string;
  /** Patient-friendly plain-English explanation. */
  desc: string;
  /** Technical description of what the AI detected. */
  info: string;
  /** Optional plain-language alias for the condition. */
  plainName?: string;
  /** Optional one-line "simply put" explainer. */
  whatIsIt?: string;
  recs: Recommendation[];
  habits: Habit[];
  prevent: PreventionTip[];
}
