'use client';

/**
 * components/ScreeningCta.tsx
 * ───────────────────────────
 * Auth-aware call to action on the landing page.
 *
 * Signed in  -> deep link into the screening tool.
 * Signed out -> sign-in / create-account prompt.
 * Replaces the `{% if user %}` branch that used to live in templates/index.html.
 */

import Link from 'next/link';

import { useAuth } from '@/hooks/useAuth';

/** Render the screening call-to-action card. */
export function ScreeningCta(): JSX.Element {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="screening-cta-card" aria-busy="true">
        <div className="cta-icon" aria-hidden="true">👁️</div>
        <h3>Loading…</h3>
        <p>Checking your session.</p>
      </div>
    );
  }

  if (user) {
    const name = user.displayName ?? user.email ?? 'there';
    return (
      <div className="screening-cta-card">
        <div className="cta-icon" aria-hidden="true">👁️</div>
        <h3>Ready to Start Your Screening</h3>
        <p>
          You&apos;re logged in as <strong>{name}</strong>. Access the full AI screening tool now.
        </p>
        <Link href="/screening" className="btn btn-primary btn-lg">
          <span aria-hidden="true">🔬</span>
          <span>Go to Eye Screening</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="screening-cta-card">
      <div className="cta-icon" aria-hidden="true">🔐</div>
      <h3>Sign In Required</h3>
      <p>
        Create a free account or sign in to access our AI-powered eye disease screening tool. Your
        privacy is protected.
      </p>
      <div className="cta-buttons">
        <Link href="/login" className="btn btn-primary btn-lg">
          <span aria-hidden="true">🔐</span>
          <span>Sign In to Screen</span>
        </Link>
        <Link href="/login?mode=register" className="btn btn-secondary btn-lg">
          <span aria-hidden="true">✨</span>
          <span>Create Account</span>
        </Link>
      </div>
      <div className="cta-trust">
        <span><span aria-hidden="true">🔒</span> Secure</span>
        <span><span aria-hidden="true">🛡️</span> Private</span>
        <span><span aria-hidden="true">✅</span> Free</span>
      </div>
    </div>
  );
}
