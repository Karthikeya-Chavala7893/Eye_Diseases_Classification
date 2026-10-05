'use client';

/**
 * components/SymptomChecklist.tsx
 * ───────────────────────────────
 * The Daily Home Mode intake form: grouped symptom checkboxes plus a live
 * escalation banner when an urgent symptom is ticked.
 *
 * Each option is a real `<input type="checkbox">` inside a `<label>`, so the
 * whole control is keyboard-navigable and screen-reader-legible without any
 * ARIA patchwork; the pill styling is applied to the label around it.
 */

import { SYMPTOM_GROUPS, hasRedFlag } from '@/lib/homeTriage';

/**
 * Render the symptom checklist.
 *
 * @param selected Currently ticked symptom ids.
 * @param onToggle Called with the id whose checkbox was clicked.
 * @param onClear Clears every selection.
 * @param disabled Locks the form while a screening is in flight.
 */
export function SymptomChecklist({
  selected,
  onToggle,
  onClear,
  disabled = false,
}: {
  selected: ReadonlySet<string>;
  onToggle: (id: string) => void;
  onClear: () => void;
  disabled?: boolean;
}): JSX.Element {
  const urgent = hasRedFlag(selected);

  return (
    <section className="symptom-panel" aria-labelledby="symptom-heading">
      <header className="symptom-header">
        <div>
          <h2 className="symptom-title" id="symptom-heading">
            What are you noticing?
          </h2>
          <p className="symptom-subtitle">
            Tick everything that applies. The more you tell us, the sharper the guidance.
          </p>
        </div>
        {selected.size > 0 && (
          <button
            type="button"
            className="symptom-clear"
            onClick={onClear}
            disabled={disabled}
          >
            Clear all ({selected.size})
          </button>
        )}
      </header>

      {urgent && (
        <div className="symptom-alert" role="alert">
          <span aria-hidden="true">🚨</span>
          <div>
            <strong>You have selected an urgent warning sign.</strong>
            <p>
              Whatever else you tick, this screening will recommend being seen by a doctor today.
              Do not wait to see whether it settles on its own.
            </p>
          </div>
        </div>
      )}

      {SYMPTOM_GROUPS.map((group) => (
        <fieldset key={group.id} className="symptom-group">
          <legend className="symptom-group-title">
            <span aria-hidden="true">{group.icon}</span> {group.title}
          </legend>
          <div className="symptom-options">
            {group.options.map((option) => {
              const checked = selected.has(option.id);
              return (
                <label
                  key={option.id}
                  className={`symptom-chip${checked ? ' checked' : ''}${option.redFlag ? ' red-flag' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => onToggle(option.id)}
                  />
                  <span className="symptom-chip-icon" aria-hidden="true">{option.icon}</span>
                  <span className="symptom-chip-label">{option.label}</span>
                </label>
              );
            })}
          </div>
        </fieldset>
      ))}
    </section>
  );
}
