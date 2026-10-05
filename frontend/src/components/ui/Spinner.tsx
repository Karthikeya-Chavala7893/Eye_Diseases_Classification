/**
 * components/ui/Spinner.tsx
 * The animated eye loader shown during AI inference.
 */

/**
 * Render the multi-ring inference loader.
 *
 * @param label Accessible status text announced to screen readers.
 */
export function Spinner({ label = 'Analyzing image' }: { label?: string }): JSX.Element {
  return (
    <div className="loader" role="status" aria-live="polite" aria-label={label}>
      <div className="loader-ring" />
      <div className="loader-ring" />
      <div className="loader-ring" />
      <span className="loader-icon" aria-hidden="true">👁️</span>
    </div>
  );
}
