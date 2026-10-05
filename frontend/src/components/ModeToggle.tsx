'use client';

/**
 * components/ModeToggle.tsx
 * ─────────────────────────
 * The segmented pill that switches the screening gateway between its two arms.
 *
 * Implemented as a real ARIA tablist so arrow keys move between modes and
 * assistive technology announces which arm is active (constraints #37 / #39).
 */

import { useRef } from 'react';

import type { ScreeningMode } from '@/types/prediction';

interface ModeOption {
  mode: ScreeningMode;
  icon: string;
  label: string;
  hint: string;
}

const MODES: readonly ModeOption[] = [
  {
    mode: 'home',
    icon: '🏠',
    label: 'Daily Home Check',
    hint: 'Symptoms + a phone photo. No clinical equipment needed.',
  },
  {
    mode: 'clinical',
    icon: '🏥',
    label: 'Clinical Retinal Scan',
    hint: 'RETFound AI analysis of a fundus or OCT retinal scan.',
  },
];

/**
 * Render the mode switcher.
 *
 * @param mode The currently active mode.
 * @param onChange Called with the newly selected mode.
 * @param disabled Locks the control while a screening is in flight.
 */
export function ModeToggle({
  mode,
  onChange,
  disabled = false,
}: {
  mode: ScreeningMode;
  onChange: (mode: ScreeningMode) => void;
  disabled?: boolean;
}): JSX.Element {
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const active = MODES.find((option) => option.mode === mode) ?? MODES[0];

  /** Move focus and selection with the left/right arrow keys. */
  const handleKeyDown = (event: React.KeyboardEvent, index: number): void => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const next = MODES[(index + delta + MODES.length) % MODES.length];
    onChange(next.mode);
    tabRefs.current[next.mode]?.focus();
  };

  return (
    <div className="mode-switch">
      <div className="mode-toggle" role="tablist" aria-label="Screening mode">
        {MODES.map((option, index) => (
          <button
            key={option.mode}
            ref={(element) => {
              tabRefs.current[option.mode] = element;
            }}
            type="button"
            role="tab"
            id={`mode-tab-${option.mode}`}
            aria-selected={mode === option.mode}
            aria-controls={`mode-panel-${option.mode}`}
            tabIndex={mode === option.mode ? 0 : -1}
            className={`mode-toggle-option${mode === option.mode ? ' active' : ''}`}
            disabled={disabled}
            onClick={() => onChange(option.mode)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            <span className="mode-toggle-icon" aria-hidden="true">{option.icon}</span>
            <span>{option.label}</span>
          </button>
        ))}
      </div>
      <p className="mode-hint">{active.hint}</p>
    </div>
  );
}
