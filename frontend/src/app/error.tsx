'use client';

import { useEffect } from 'react';

/**
 * app/error.tsx
 * Route-level error boundary.
 *
 * Shows a recovery action instead of a blank screen and never renders the raw
 * stack trace to the user.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): JSX.Element {
  useEffect(() => {
    // Surfaced in the browser console for debugging; not shown to the user.
    console.error('Unhandled application error:', error);
  }, [error]);

  return (
    <main className="screening-main">
      <div className="container">
        <div className="welcome-section" role="alert">
          <div style={{ fontSize: '3rem' }} aria-hidden="true">😔</div>
          <h1 className="welcome-title">Something Went Wrong</h1>
          <p className="welcome-subtitle">
            An unexpected error interrupted this page. Please try again.
          </p>
          <p style={{ marginTop: 'var(--space-6)' }}>
            <button type="button" className="btn btn-primary btn-lg" onClick={reset}>
              <span aria-hidden="true">🔄</span>
              <span>Try Again</span>
            </button>
          </p>
        </div>
      </div>
    </main>
  );
}
