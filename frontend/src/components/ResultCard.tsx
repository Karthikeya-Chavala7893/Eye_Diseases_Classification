'use client';

/**
 * components/ResultCard.tsx
 * ─────────────────────────
 * Collapsible diagnosis card for one predicted condition.
 *
 * Ported from the `showResults()` DOM builder in static/js/screening.js, with
 * the innerHTML string templates replaced by real, escaped React elements
 * (no dangerouslySetInnerHTML anywhere) and semantic <article> markup with
 * proper heading hierarchy (constraint #41).
 */

import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { getConfidenceLevel } from '@/components/ConfidenceBar';
import { getDisease } from '@/lib/diseases';
import type { PredictionResult } from '@/types/prediction';

/** Which detail panel is showing inside an expanded card. */
type TabKey = 'recs' | 'habits' | 'prevent';

const CLINICAL_TABS: ReadonlyArray<{ key: TabKey; icon: string; label: string }> = [
  { key: 'recs', icon: '📋', label: 'Recommendations' },
  { key: 'habits', icon: '🌟', label: 'Daily Habits' },
  { key: 'prevent', icon: '🛡️', label: 'Prevention' },
];

/**
 * Home cards give guidance you act on yourself, so the first tab is worded as
 * such. The urgent card calls it an action plan instead of guidance.
 */
const HOME_TABS: ReadonlyArray<{ key: TabKey; icon: string; label: string }> = [
  { key: 'recs', icon: '🏠', label: 'Home Guidance' },
  { key: 'habits', icon: '🌟', label: 'Daily Habits' },
  { key: 'prevent', icon: '🛡️', label: 'Prevention' },
];

/** Confidence below which a clinical card is de-emphasised as unlikely. */
const LOW_CONFIDENCE_THRESHOLD = 30;

/**
 * Render one expandable prediction card.
 *
 * @param prediction The label/confidence pair from the model or triage engine.
 * @param index Position in the results list; index 0 starts expanded.
 * @param variant Which knowledge base and vocabulary to render with. Home cards
 *   report a symptom *match*, not a model confidence, so the probability
 *   language and the low-confidence de-emphasis are both suppressed.
 */
export function ResultCard({
  prediction,
  index,
  variant = 'clinical',
}: {
  prediction: PredictionResult;
  index: number;
  variant?: 'clinical' | 'home';
}): JSX.Element {
  const disease = getDisease(prediction.label);
  const [expanded, setExpanded] = useState<boolean>(index === 0);
  const [tab, setTab] = useState<TabKey>('recs');
  const confidenceInfo = getConfidenceLevel(prediction.confidence);

  const isHome = variant === 'home';
  const tabs = isHome ? HOME_TABS : CLINICAL_TABS;
  const bodyId = `disease-body-${index}`;

  return (
    <article className={`disease-card${expanded ? ' expanded' : ''}`} id={`card-${index}`}>
      <div
        className="disease-card-header"
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => setExpanded((open) => !open)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setExpanded((open) => !open);
          }
        }}
      >
        <div className={`disease-icon-wrapper ${disease.severity}`}>
          <span className="disease-icon" aria-hidden="true">{disease.icon}</span>
        </div>
        <div className="disease-info">
          <h4 className="disease-name">{disease.name}</h4>
          {/* Fix A: Suppress alarming severity badge when AI confidence is low.
              Home cards are a symptom match, not a probability, so their badge
              always stands. */}
          {!isHome && prediction.confidence < LOW_CONFIDENCE_THRESHOLD ? (
            <span
              className="disease-severity"
              style={{
                background: 'rgba(107,114,128,0.12)',
                color: '#6b7280',
                border: '1px solid rgba(107,114,128,0.2)',
                padding: '0.125rem 0.5rem',
                borderRadius: '999px',
                fontSize: '0.7rem',
                fontWeight: 600,
              }}
            >
              ⚪ Low Probability
            </span>
          ) : (
            <Badge severity={disease.severity} badge={disease.badge} />
          )}
        </div>
        <div className="disease-confidence">
          <span className="confidence-value">{prediction.confidence.toFixed(1)}%</span>
          {isHome ? (
            <span
              className="confidence-level-badge"
              style={{
                padding: '0.15rem 0.5rem',
                borderRadius: '999px',
                background: 'var(--gray-100)',
                color: 'var(--gray-500)',
                fontWeight: 600,
                fontSize: '0.65rem',
                letterSpacing: '0.02em',
                marginTop: '0.125rem',
              }}
            >
              {prediction.is_healthy
                ? 'normal'
                : prediction.source === 'photo_only'
                  ? 'photo cue'
                  : prediction.source === 'ai_model'
                    ? 'AI match'
                    : 'symptom match'}
            </span>
          ) : (
            <span
              className="confidence-level-badge"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                padding: '0.15rem 0.5rem',
                borderRadius: '999px',
                background: confidenceInfo.bgColor,
                color: confidenceInfo.color,
                fontWeight: 600,
                fontSize: '0.65rem',
                letterSpacing: '0.02em',
                marginTop: '0.125rem',
              }}
            >
              {confidenceInfo.emoji} {confidenceInfo.level}
            </span>
          )}
        </div>
        <span className="expand-icon" aria-hidden="true">▼</span>
      </div>

      <div className="disease-card-body" id={bodyId}>
        {disease.covers && (
          <p className="disease-covers">
            <strong>What this covers:</strong> {disease.covers}
          </p>
        )}
        <p style={{ color: 'var(--gray-500)', marginBottom: 'var(--space-5)', lineHeight: 1.7 }}>
          {disease.info}
        </p>

        <div className="info-tabs" role="tablist" aria-label={`${disease.name} details`}>
          {tabs.map((entry) => (
            <button
              key={entry.key}
              type="button"
              role="tab"
              id={`tab-${entry.key}-${index}`}
              aria-selected={tab === entry.key}
              aria-controls={`panel-${entry.key}-${index}`}
              className={`info-tab${tab === entry.key ? ' active' : ''}`}
              onClick={() => setTab(entry.key)}
            >
              <span aria-hidden="true">{entry.icon}</span> {entry.label}
            </button>
          ))}
        </div>

        <div
          className={`tab-content${tab === 'recs' ? ' active' : ''}`}
          id={`panel-recs-${index}`}
          role="tabpanel"
          aria-labelledby={`tab-recs-${index}`}
        >
          {disease.recs.length === 0 ? (
            <p>No recommendations.</p>
          ) : (
            <div className="recommendation-grid">
              {disease.recs.map((rec) => (
                <div key={rec.title} className={`recommendation-card ${rec.priority ?? ''}`}>
                  <span className="recommendation-icon" aria-hidden="true">{rec.icon}</span>
                  <h5 className="recommendation-title">{rec.title}</h5>
                  <p className="recommendation-text">{rec.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div
          className={`tab-content${tab === 'habits' ? ' active' : ''}`}
          id={`panel-habits-${index}`}
          role="tabpanel"
          aria-labelledby={`tab-habits-${index}`}
        >
          {disease.habits.length === 0 ? (
            <p>No habits.</p>
          ) : (
            <div className="habits-list">
              {disease.habits.map((habit) => (
                <div key={habit.title} className="habit-item">
                  <div className="habit-icon-wrapper">
                    <span className="habit-icon" aria-hidden="true">{habit.icon}</span>
                  </div>
                  <div className="habit-content">
                    <h5 className="habit-title">{habit.title}</h5>
                    <p className="habit-description">{habit.desc}</p>
                    <span className="habit-frequency">
                      <span aria-hidden="true">🕐</span>
                      <span>{habit.freq}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div
          className={`tab-content${tab === 'prevent' ? ' active' : ''}`}
          id={`panel-prevent-${index}`}
          role="tabpanel"
          aria-labelledby={`tab-prevent-${index}`}
        >
          {disease.prevent.length === 0 ? (
            <p>No tips.</p>
          ) : (
            <div className="prevention-tips">
              {disease.prevent.map((tip) => (
                <div key={tip.title} className="prevention-tip">
                  <span className="prevention-icon" aria-hidden="true">{tip.icon}</span>
                  <h5 className="prevention-title">{tip.title}</h5>
                  <p className="prevention-text">{tip.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
