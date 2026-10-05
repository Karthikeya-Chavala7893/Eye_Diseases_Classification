/**
 * lib/homeTriage.ts
 * ─────────────────
 * The Daily Home Mode symptom checklist.
 *
 * These ids are the wire contract with `backend/triage.py`. The backend owns
 * the scoring weights; this file owns only how each symptom is worded and
 * grouped for the patient. Never rename an id here without renaming it there
 * in the same commit — an id the backend does not recognise is silently
 * discarded, so a drift would fail quietly rather than loudly.
 */

/** One tickable symptom in the home checklist. */
export interface SymptomOption {
  /** Wire id, matching a key of `SYMPTOM_WEIGHTS` in backend/triage.py. */
  id: string;
  /** Patient-facing wording, written in the second person. */
  label: string;
  icon: string;
  /**
   * Urgent symptoms. Ticking one forces the red-alert card to the top of the
   * results, however many mild boxes are also ticked, and the UI marks them so
   * the patient understands why.
   */
  redFlag?: boolean;
}

/** A titled block of related symptoms in the checklist. */
export interface SymptomGroup {
  id: string;
  title: string;
  icon: string;
  options: SymptomOption[];
}

/** The full checklist, in the order it is presented. */
export const SYMPTOM_GROUPS: readonly SymptomGroup[] = [
  {
    id: 'comfort',
    title: 'Itching & irritation',
    icon: '🌿',
    options: [
      { id: 'itching', icon: '🖐️', label: 'Itchy eyes I keep wanting to rub' },
      { id: 'watering', icon: '💧', label: 'Watery eyes or constant tearing' },
      { id: 'seasonal_allergies', icon: '🤧', label: 'Sneezing, runny nose or known seasonal allergies' },
      { id: 'puffy_lids', icon: '😣', label: 'Puffy or swollen eyelids' },
      { id: 'gritty_feeling', icon: '⏳', label: 'A gritty, sandy feeling under the lids' },
    ],
  },
  {
    id: 'screens',
    title: 'Screens & dryness',
    icon: '📱',
    options: [
      { id: 'long_screen_hours', icon: '💻', label: 'Six or more hours of screen time most days' },
      { id: 'evening_burning', icon: '🔥', label: 'Burning or tired eyes by the evening' },
      { id: 'dryness', icon: '🏜️', label: 'Persistent dryness' },
      { id: 'headache_after_screens', icon: '🤕', label: 'Headaches after long screen sessions' },
      { id: 'blur_clears_on_rest', icon: '😑', label: 'Blurring that clears when I look away' },
    ],
  },
  {
    id: 'redness',
    title: 'Redness & discharge',
    icon: '🩸',
    options: [
      { id: 'redness', icon: '🔴', label: 'Bloodshot or red whites of the eye' },
      { id: 'crusty_discharge', icon: '🟡', label: 'Crusty or yellow discharge on waking' },
      { id: 'contagious_contact', icon: '🏠', label: 'Someone around me has pink eye' },
      { id: 'contact_lens_discomfort', icon: '👁️', label: 'My contact lenses have become uncomfortable' },
      { id: 'blood_patch', icon: '🩹', label: 'A bright red patch on the white of the eye' },
    ],
  },
  {
    id: 'clarity',
    title: 'Cloudiness & night vision',
    icon: '🌫️',
    options: [
      { id: 'cloudy_pupil', icon: '⚪', label: 'Milky or grey clouding visible over the pupil' },
      { id: 'faded_colours', icon: '🎨', label: 'Colours look faded or yellowed' },
      { id: 'night_halos', icon: '🚗', label: 'Halos or starbursts around headlights at night' },
      { id: 'age_60_plus', icon: '🎂', label: 'Aged 60 or above' },
      { id: 'double_vision_one_eye', icon: '👀', label: 'Double vision in one eye, even with the other closed' },
    ],
  },
  {
    id: 'urgent',
    title: 'Urgent warning signs',
    icon: '🚨',
    options: [
      { id: 'sudden_blur', icon: '⚡', label: 'Sudden blurring or loss of vision', redFlag: true },
      { id: 'floaters_or_flashes', icon: '🕸️', label: 'New floating dark webs, spots or flashes of light', redFlag: true },
      { id: 'tunnel_vision', icon: '🔦', label: 'My field of vision is narrowing, like a tunnel', redFlag: true },
      { id: 'severe_pain_nausea', icon: '🤢', label: 'Severe eye pain, with headache or nausea', redFlag: true },
      { id: 'diabetes_or_bp', icon: '🩺', label: 'Diagnosed diabetes or high blood pressure' },
    ],
  },
];

/** Every symptom id the checklist can submit. */
export const ALL_SYMPTOM_IDS: readonly string[] = SYMPTOM_GROUPS.flatMap((group) =>
  group.options.map((option) => option.id),
);

/** Ids that trigger the red-alert escalation, mirroring RED_FLAG_SYMPTOMS. */
export const RED_FLAG_IDS: ReadonlySet<string> = new Set(
  SYMPTOM_GROUPS.flatMap((group) => group.options.filter((o) => o.redFlag).map((o) => o.id)),
);

/**
 * Report whether a selection contains an urgent symptom.
 *
 * Used to surface the escalation banner the moment a box is ticked, before the
 * request is even sent.
 *
 * @param selected Currently ticked symptom ids.
 * @returns True when at least one red-flag symptom is selected.
 */
export function hasRedFlag(selected: Iterable<string>): boolean {
  for (const id of selected) {
    if (RED_FLAG_IDS.has(id)) return true;
  }
  return false;
}
