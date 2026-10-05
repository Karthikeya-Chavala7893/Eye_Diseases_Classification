import Link from 'next/link';

/**
 * components/Footer.tsx
 * Full site footer (landing page) and the minimal variant used elsewhere.
 * Ported from templates/index.html and templates/screening.html.
 */

/** Compact one-line footer used on the screening and auth pages. */
export function MinimalFooter(): JSX.Element {
  return (
    <footer className="footer-minimal">
      <div className="container">
        <p>&copy; 2024 VisionAI Eye Hospital. For educational purposes only.</p>
      </div>
    </footer>
  );
}

/** Full multi-column footer used on the landing page. */
export function Footer(): JSX.Element {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-brand">
            <Link href="/" className="footer-logo">
              <span className="logo-icon" aria-hidden="true">👁️</span>
              <span className="logo-text">
                Vision<span className="logo-accent">AI</span>
              </span>
            </Link>
            <p className="footer-tagline">
              AI-powered eye disease detection for a healthier tomorrow.
            </p>
          </div>

          <div className="footer-links">
            <h4>Product</h4>
            <Link href="#features">Features</Link>
            <Link href="#how-it-works">How It Works</Link>
            <Link href="/screening">AI Screening</Link>
          </div>

          <div className="footer-links">
            <h4>Resources</h4>
            <Link href="#awareness">Eye Health</Link>
            <Link href="#awareness">Prevention Tips</Link>
            <Link href="#screening">Get Screened</Link>
          </div>

          <div className="footer-links">
            <h4>Account</h4>
            <Link href="/login">Sign In</Link>
            <Link href="/login">Create Account</Link>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; 2024 VisionAI Eye Hospital. All rights reserved.</p>
          <p className="footer-disclaimer">
            For educational and research purposes. Not a substitute for professional medical advice.
          </p>
        </div>
      </div>
    </footer>
  );
}
