'use client';

/**
 * components/ui/Toast.tsx
 * Inline alert banner used by the auth forms.
 */

/** Visual tone of the alert. */
export type ToastKind = 'error' | 'success';

/**
 * Render a dismissible inline alert.
 *
 * @param kind Whether the message reports a failure or a success.
 * @param message Text to display; the banner hides when empty.
 */
export function Toast({ kind, message }: { kind: ToastKind; message: string | null }): JSX.Element | null {
  if (!message) return null;
  return (
    <div className={`auth-alert show ${kind}`} role="alert" aria-live="assertive">
      <span className="alert-icon" aria-hidden="true">{kind === 'error' ? '⚠️' : '✅'}</span>
      <span className="alert-message">{message}</span>
    </div>
  );
}
