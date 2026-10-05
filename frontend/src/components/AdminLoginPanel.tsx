'use client';

/**
 * components/AdminLoginPanel.tsx
 * ─────────────────────────────
 * Admin login form. Verifies the `admin` custom claim after sign-in.
 * Non-admin users are signed out with an error message.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

import { Toast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { verifyAdmin } from '@/lib/api';

export function AdminLoginPanel(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading, configured, error, signInWithEmail, signInWithGoogle, logout } =
    useAuth();

  const nextPath = searchParams.get('next') ?? '/admin/dashboard';
  const [busy, setBusy] = useState<boolean>(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState<boolean>(false);

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  // If already signed in and admin, redirect straight to dashboard
  useEffect(() => {
    if (!loading && user) {
      verifyAdmin(user)
        .then((data) => {
          if (data.isAdmin) {
            router.replace(nextPath);
          }
        })
        .catch(() => {
          // Not admin or backend down — stay on login page
        });
    }
  }, [loading, user, nextPath, router]);

  const verifyAndRedirect = async (): Promise<void> => {
    if (!user) return;
    try {
      await user.getIdToken(true);
      const data = await verifyAdmin(user);
      if (data.isAdmin) {
        setNotice('Admin verified! Redirecting…');
        router.replace(nextPath);
      } else {
        setAdminError('You do not have admin privileges. Contact the platform administrator.');
        await logout();
      }
    } catch {
      setAdminError('Unable to verify admin status. Make sure the backend is running.');
      await logout();
    }
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    setAdminError(null);
    try {
      await signInWithEmail(email.trim().toLowerCase(), password);
      setTimeout(() => verifyAndRedirect(), 500);
    } catch {
      // error is set by AuthContext
    } finally {
      setBusy(false);
    }
  };

  const handleGoogle = async (): Promise<void> => {
    setBusy(true);
    setNotice(null);
    setAdminError(null);
    try {
      await signInWithGoogle();
      setTimeout(() => verifyAndRedirect(), 500);
    } catch {
      // error is set by AuthContext
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-container">
      <Link href="/" className="back-link">
        <span aria-hidden="true">←</span>
        <span>Back to Home</span>
      </Link>

      <div className="auth-card">
        <div className="auth-header">
          <Link href="/" className="auth-logo">
            <span className="logo-icon" aria-hidden="true">🛡️</span>
            <span className="logo-text">
              Vision<span className="logo-accent">AI</span>
            </span>
          </Link>
          <h1 className="auth-title">Admin Access</h1>
          <p className="auth-subtitle">Sign in with your admin credentials</p>
        </div>

        <Toast kind="success" message={notice} />
        <Toast kind="error" message={adminError ?? error} />

        {!configured && (
          <p className="form-error show" role="alert">
            Firebase is not configured. Copy <code>frontend/.env.example</code> to{' '}
            <code>frontend/.env.local</code> and fill in the NEXT_PUBLIC_FIREBASE_* values.
          </p>
        )}

        <form className="auth-form active" onSubmit={handleLogin} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="adminEmail">
              Admin Email
            </label>
            <input
              id="adminEmail"
              type="email"
              className="form-input"
              placeholder="admin@example.com"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="adminPassword">
              Password
            </label>
            <div className="password-toggle">
              <input
                id="adminPassword"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="Enter your password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="toggle-btn"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className={`auth-btn auth-btn-primary${busy ? ' btn-loading' : ''}`}
            disabled={busy || !configured}
          >
            <span aria-hidden="true">🛡️</span>
            <span>Admin Sign In</span>
          </button>
        </form>

        <div className="auth-divider">or continue with</div>

        <button
          type="button"
          className="google-btn"
          onClick={handleGoogle}
          disabled={busy || !configured}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          <span>Continue with Google</span>
        </button>

        <div className="auth-trust">
          <div className="trust-badge">
            <span aria-hidden="true">🛡️</span>
            <span>Admin Only</span>
          </div>
          <div className="trust-badge">
            <span aria-hidden="true">🔐</span>
            <span>Role Verified</span>
          </div>
          <div className="trust-badge">
            <span aria-hidden="true">🔒</span>
            <span>Custom Claims</span>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: '1rem' }}>
          <Link href="/login" className="nav-link" style={{ fontSize: '0.875rem' }}>
            ← User Login
          </Link>
        </div>
      </div>
    </div>
  );
}
