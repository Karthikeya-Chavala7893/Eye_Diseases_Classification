/**
 * components/ConfidenceBar.tsx
 * ────────────────────────────
 * Animated confidence meter with human-readable level indicator.
 * Replaces the raw "match score" with intuitive color-coded feedback.
 */

/** Return a human-readable confidence level and associated color. */
export function getConfidenceLevel(value: number): {
  level: string;
  color: string;
  bgColor: string;
  emoji: string;
  gradient: string;
} {
  if (value >= 75) {
    return {
      level: 'High',
      color: '#059669',
      bgColor: 'rgba(5, 150, 105, 0.12)',
      emoji: '🟢',
      gradient: 'linear-gradient(90deg, #34d399, #059669)',
    };
  }
  if (value >= 40) {
    return {
      level: 'Moderate',
      color: '#d97706',
      bgColor: 'rgba(217, 119, 6, 0.12)',
      emoji: '🟡',
      gradient: 'linear-gradient(90deg, #fbbf24, #d97706)',
    };
  }
  return {
    level: 'Low',
    color: '#6b7280',
    bgColor: 'rgba(107, 114, 128, 0.12)',
    emoji: '⚪',
    gradient: 'linear-gradient(90deg, #d1d5db, #9ca3af)',
  };
}

/**
 * Render an accessible progress bar for a confidence percentage.
 *
 * @param value Confidence, 0–100.
 * @param label Accessible name describing what the bar measures.
 * @param gradient CSS background applied to the filled portion (auto-colored by level if omitted).
 * @param showLevel Whether to show the human-readable level badge.
 */
export function ConfidenceBar({
  value,
  label,
  gradient,
  showLevel = false,
}: {
  value: number;
  label: string;
  gradient?: string;
  showLevel?: boolean;
}): JSX.Element {
  const clamped = Math.min(Math.max(value, 0), 100);
  const info = getConfidenceLevel(clamped);
  const barGradient = gradient ?? info.gradient;

  return (
    <div style={{ width: '100%' }}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          height: 10,
          background: 'rgba(255,255,255,0.3)',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${clamped}%`,
            background: barGradient,
            borderRadius: 'var(--radius-full)',
            transition: 'width 700ms cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      </div>
      {showLevel && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            marginTop: '0.375rem',
            fontSize: '0.75rem',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              padding: '0.125rem 0.5rem',
              borderRadius: '999px',
              background: info.bgColor,
              color: info.color,
              fontWeight: 600,
              fontSize: '0.7rem',
              letterSpacing: '0.02em',
            }}
          >
            {info.emoji} {info.level} confidence
          </span>
        </div>
      )}
    </div>
  );
}
