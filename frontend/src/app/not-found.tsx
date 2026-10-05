import Link from 'next/link';

/**
 * app/not-found.tsx
 * 404 page rendered for any unmatched route.
 */
export default function NotFound(): JSX.Element {
  return (
    <main className="screening-main">
      <div className="container">
        <div className="welcome-section">
          <div style={{ fontSize: '3rem' }} aria-hidden="true">🔍</div>
          <h1 className="welcome-title">Page Not Found</h1>
          <p className="welcome-subtitle">
            We couldn&apos;t find the page you were looking for.
          </p>
          <p style={{ marginTop: 'var(--space-6)' }}>
            <Link href="/" className="btn btn-primary btn-lg">
              <span aria-hidden="true">🏠</span>
              <span>Back to Home</span>
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
