/**
 * components/ui/Badge.tsx
 * Severity pill used on result cards.
 *
 * Clinical results use the three-band severity scale and its CSS classes. Home
 * triage cards carry five urgency bands, so they pass an explicit `badge`
 * override with its own wording and colours.
 */

import type { BadgeStyle, Severity } from '@/types/prediction';

/**
 * Render a coloured severity badge.
 *
 * @param severity Severity band driving the colour class.
 * @param badge Optional five-band override supplying its own label and colours.
 * @param children Label text; defaults to the badge label, else the capitalised severity.
 */
export function Badge({
  severity,
  badge,
  children,
}: {
  severity: Severity;
  badge?: BadgeStyle;
  children?: React.ReactNode;
}): JSX.Element {
  if (badge) {
    return (
      <span
        className="disease-severity"
        style={{ background: badge.background, color: badge.color }}
      >
        {children ?? badge.label}
      </span>
    );
  }

  const label = severity.charAt(0).toUpperCase() + severity.slice(1);
  return <span className={`disease-severity ${severity}`}>{children ?? label}</span>;
}
