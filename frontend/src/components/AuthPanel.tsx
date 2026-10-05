'use client';

/**
 * components/AuthPanel.tsx
 * ────────────────────────
 * Authentication card redesigned to match the clean segmented layout:
 * - Brand logo + "Trusted Companion" subtitle
 * - Top [ User | Admin ] segmented role toggle
 * - Icon-prefixed input fields (Email ✉️, Password 🔒, Name 👤)
 * - Primary Action Button with ➔ icon
 * - "OR" divider + Google Sign-In button
 * - "Don't have an account? Create Account" toggle
 * - "Forgot Password?" & "Need Help?" footer links
 * - "🛡️ Secure Authentication" trust badge
 * - "© 2026 VisionAI. All rights reserved." bottom footer
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import type { User } from 'firebase/auth';

import { Toast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { verifyAdmin } from '@/lib/api';

type Role = 'user' | 'admin';
type Mode = 'login' | 'register';

const MIN_PASSWORD_LENGTH = 8;

export function AuthPanel(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    user,
    loading,
    configured,
    error,
    clearError,
    signInWithEmail,
    registerWithEmail,
    signInWithGoogle,
    resetPassword,
    logout,
  } = useAuth();

  const initialRole: Role = searchParams.get('role') === 'admin' ? 'admin' : 'user';
  const [role, setRole] = useState<Role>(initialRole);
  const [mode, setMode] = useState<Mode>(
    searchParams.get('mode') === 'register' ? 'register' : 'login',
  );

  const nextPath = searchParams.get('next') ?? (role === 'admin' ? '/admin/dashboard' : '/screening');

  const [busy, setBusy] = useState<boolean>(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [name, setName] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [fieldError, setFieldError] = useState<string | null>(null);

  // Modals / Helpers
  const [showHelpModal, setShowHelpModal] = useState<boolean>(false);
  const [showForgotModal, setShowForgotModal] = useState<boolean>(false);
  const [forgotEmail, setForgotEmail] = useState<string>('');
  const [forgotSuccess, setForgotSuccess] = useState<boolean>(false);

  // If already logged in, redirect
  useEffect(() => {
    if (!loading && user) {
      if (role === 'admin') {
        verifyAdmin(user)
          .then((data) => {
            if (data.isAdmin) router.replace(nextPath);
          })
          .catch(() => {
            // Not verified as admin
          });
      } else {
        router.replace(nextPath);
      }
    }
  }, [loading, user, nextPath, router, role]);

  const switchRole = (newRole: Role): void => {
    setRole(newRole);
    setFieldError(null);
    setAdminError(null);
    setNotice(null);
    clearError();
    if (newRole === 'admin') {
      setMode('login'); // Admins only sign in
    }
  };

  const switchMode = (newMode: Mode): void => {
    setMode(newMode);
    setFieldError(null);
    setAdminError(null);
    setNotice(null);
    clearError();
  };

  const toggleVisibility = (field: string): void =>
    setShowPassword((curr) => ({ ...curr, [field]: !curr[field] }));

  const verifyAndRedirectAdmin = async (targetUser: User | null): Promise<void> => {
    if (!targetUser) return;
    try {
      await targetUser.getIdToken(true);
      const data = await verifyAdmin(targetUser);
      if (data.isAdmin) {
        setNotice('Admin verified! Redirecting to dashboard…');
        router.replace('/admin/dashboard');
      } else {
        setAdminError('You do not have admin privileges. Access restricted.');
        await logout();
      }
    } catch {
      setAdminError('Unable to verify admin status. Make sure the backend is running on http://localhost:5000.');
      await logout();
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setFieldError(null);
    setAdminError(null);
    setNotice(null);

    const cleanEmail = email.trim().toLowerCase();

    // Validation
    if (!cleanEmail) {
      setFieldError('Please enter your email address');
      return;
    }
    if (!password) {
      setFieldError('Please enter your password');
      return;
    }

    if (role === 'user' && mode === 'register') {
      if (!name.trim()) {
        setFieldError('Please enter your full name');
        return;
      }
      if (password.length < MIN_PASSWORD_LENGTH) {
        setFieldError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
        return;
      }
      if (password !== confirmPassword) {
        setFieldError('Passwords do not match');
        return;
      }

      setBusy(true);
      try {
        await registerWithEmail(name.trim(), cleanEmail, password);
        setNotice('Account created successfully! Redirecting…');
        // Small tick so the session cookie written by AuthContext propagates
        // to the browser before the middleware evaluates the next route.
        await new Promise((resolve) => setTimeout(resolve, 150));
        router.replace(nextPath);
      } catch {
        // Error set by AuthContext
      } finally {
        setBusy(false);
      }
      return;
    }

    // Sign In (User or Admin)
    setBusy(true);
    try {
      const loggedUser = await signInWithEmail(cleanEmail, password);
      if (role === 'admin') {
        await verifyAndRedirectAdmin(loggedUser);
      } else {
        setNotice('Login successful! Redirecting…');
        // Small tick so the session cookie written by AuthContext propagates
        // to the browser before the middleware evaluates the next route.
        await new Promise((resolve) => setTimeout(resolve, 150));
        router.replace(nextPath);
      }
    } catch {
      // Error set by AuthContext
    } finally {
      setBusy(false);
    }
  };

  const handleGoogle = async (): Promise<void> => {
    setBusy(true);
    setFieldError(null);
    setAdminError(null);
    setNotice(null);
    try {
      const loggedUser = await signInWithGoogle();
      if (role === 'admin') {
        await verifyAndRedirectAdmin(loggedUser);
      } else {
        // Small tick so the session cookie written by AuthContext propagates
        // to the browser before the middleware evaluates the next route.
        await new Promise((resolve) => setTimeout(resolve, 150));
        router.replace(nextPath);
      }
    } catch {
      // Error handled by AuthContext
    } finally {
      setBusy(false);
    }
  };

  const handleForgotPassword = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    const targetEmail = (forgotEmail || email).trim().toLowerCase();
    if (!targetEmail) {
      setFieldError('Please enter your email address to reset password');
      return;
    }
    setBusy(true);
    try {
      await resetPassword(targetEmail);
      setForgotSuccess(true);
      setNotice(`Password reset link sent to ${targetEmail}`);
      setTimeout(() => {
        setShowForgotModal(false);
        setForgotSuccess(false);
      }, 3000);
    } catch (err) {
      setFieldError(err instanceof Error ? err.message : 'Failed to send reset email');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ref-auth-page">
      <div className="ref-auth-container">
        {/* Back Link */}
        <Link href="/" className="ref-back-link">
          <span aria-hidden="true">←</span>
          <span>Back to Home</span>
        </Link>

        {/* Main Card */}
        <div className="ref-auth-card">
          {/* Header */}
          <div className="ref-header">
            <Link href="/" className="ref-brand">
              <span className="ref-logo-icon">👁️</span>
              <span className="ref-brand-name">
                Vision<span className="ref-brand-accent">AI</span>
              </span>
            </Link>
            <p className="ref-subtitle">Trusted Screening Companion</p>
          </div>

          {/* Segmented Role Switcher [ User | Admin ] */}
          <div className="ref-role-tabs" role="tablist" aria-label="Account Role">
            <button
              type="button"
              role="tab"
              aria-selected={role === 'user'}
              className={`ref-role-tab${role === 'user' ? ' active' : ''}`}
              onClick={() => switchRole('user')}
            >
              User
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={role === 'admin'}
              className={`ref-role-tab${role === 'admin' ? ' active' : ''}`}
              onClick={() => switchRole('admin')}
            >
              Admin
            </button>
          </div>

          {/* Feedback Toasts */}
          <Toast kind="success" message={notice} />
          <Toast kind="error" message={fieldError ?? adminError ?? error} />

          {!configured && (
            <p className="ref-config-alert" role="alert">
              Firebase is not configured. Copy <code>frontend/.env.example</code> to{' '}
              <code>frontend/.env.local</code> and fill in credentials.
            </p>
          )}

          {/* Form */}
          <form className="ref-form" onSubmit={handleSubmit} noValidate>
            {/* Registration Full Name (Only when User + Register) */}
            {role === 'user' && mode === 'register' && (
              <div className="ref-field">
                <label className="ref-label" htmlFor="fullName">
                  Full Name
                </label>
                <div className="ref-input-wrap">
                  <span className="ref-input-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  </span>
                  <input
                    id="fullName"
                    type="text"
                    className="ref-input"
                    placeholder="John Doe"
                    autoComplete="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* Email Address */}
            <div className="ref-field">
              <label className="ref-label" htmlFor="authEmail">
                Email Address
              </label>
              <div className="ref-input-wrap">
                <span className="ref-input-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect width="20" height="16" x="2" y="4" rx="2" />
                    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                  </svg>
                </span>
                <input
                  id="authEmail"
                  type="email"
                  className="ref-input"
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            {/* Password */}
            <div className="ref-field">
              <label className="ref-label" htmlFor="authPassword">
                Password
              </label>
              <div className="ref-input-wrap">
                <span className="ref-input-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </span>
                <input
                  id="authPassword"
                  type={showPassword.main ? 'text' : 'password'}
                  className="ref-input"
                  placeholder={mode === 'register' ? `Min ${MIN_PASSWORD_LENGTH} characters` : '••••••••'}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="ref-suffix-btn"
                  onClick={() => toggleVisibility('main')}
                  aria-label={showPassword.main ? 'Hide password' : 'Show password'}
                >
                  {showPassword.main ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Confirm Password (Register mode) */}
            {role === 'user' && mode === 'register' && (
              <div className="ref-field">
                <label className="ref-label" htmlFor="confirmPassword">
                  Confirm Password
                </label>
                <div className="ref-input-wrap">
                  <span className="ref-input-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  </span>
                  <input
                    id="confirmPassword"
                    type={showPassword.confirm ? 'text' : 'password'}
                    className="ref-input"
                    placeholder="Repeat your password"
                    autoComplete="new-password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="ref-suffix-btn"
                    onClick={() => toggleVisibility('confirm')}
                    aria-label={showPassword.confirm ? 'Hide password' : 'Show password'}
                  >
                    {showPassword.confirm ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>
            )}

            {/* Primary Action Button */}
            <button
              type="submit"
              className={`ref-primary-btn${busy ? ' loading' : ''}`}
              disabled={busy || !configured}
            >
              <span className="ref-btn-icon" aria-hidden="true">
                {role === 'admin' ? '🛡️' : mode === 'register' ? '✨' : '➔'}
              </span>
              <span>
                {role === 'admin'
                  ? 'Admin Sign In'
                  : mode === 'register'
                  ? 'Create Account'
                  : 'Sign In'}
              </span>
            </button>
          </form>

          {/* Divider */}
          <div className="ref-divider">
            <span>OR</span>
          </div>

          {/* Google Sign-In Button */}
          <button
            type="button"
            className="ref-google-btn"
            onClick={handleGoogle}
            disabled={busy || !configured}
          >
            <svg viewBox="0 0 24 24" className="ref-google-icon" aria-hidden="true">
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
            <span>Sign in with Google</span>
          </button>

          {/* Account Mode Switch Link */}
          {role === 'user' ? (
            <div className="ref-switch-link">
              {mode === 'login' ? (
                <>
                  <span>Don&apos;t have an account? </span>
                  <button
                    type="button"
                    className="ref-link-btn"
                    onClick={() => switchMode('register')}
                  >
                    Create Account
                  </button>
                </>
              ) : (
                <>
                  <span>Already have an account? </span>
                  <button
                    type="button"
                    className="ref-link-btn"
                    onClick={() => switchMode('login')}
                  >
                    Sign In
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="ref-switch-link">
              <span style={{ fontSize: '0.8rem', opacity: 0.75 }}>
                Admin access restricted to verified credentials
              </span>
            </div>
          )}

          {/* Bottom Divider & Action Links */}
          <div className="ref-card-footer">
            <button
              type="button"
              className="ref-footer-link"
              onClick={() => {
                setForgotEmail(email);
                setShowForgotModal(true);
              }}
            >
              Forgot Password?
            </button>

            <button
              type="button"
              className="ref-footer-link ref-help-link"
              onClick={() => setShowHelpModal(true)}
            >
              <span aria-hidden="true">❔</span>
              <span>Need Help?</span>
            </button>
          </div>

          {/* Trust Badge */}
          <div className="ref-trust-badge">
            <span className="ref-trust-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </span>
            <span>Secure Authentication</span>
          </div>
        </div>

        {/* Page Copyright Footer */}
        <p className="ref-page-copyright">
          © {new Date().getFullYear()} VisionAI. All rights reserved.
        </p>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="ref-modal-backdrop" onClick={() => setShowForgotModal(false)}>
          <div className="ref-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ref-modal-header">
              <h3 className="ref-modal-title">Reset Password</h3>
              <button
                type="button"
                className="ref-modal-close"
                onClick={() => setShowForgotModal(false)}
              >
                ✕
              </button>
            </div>
            <p className="ref-modal-desc">
              Enter your email address and we will send you a secure link to reset your password.
            </p>
            {forgotSuccess ? (
              <div className="ref-modal-success">
                ✅ Reset email sent! Please check your inbox.
              </div>
            ) : (
              <form onSubmit={handleForgotPassword}>
                <div className="ref-field" style={{ marginBottom: '1.25rem' }}>
                  <label className="ref-label" htmlFor="resetEmail">
                    Email Address
                  </label>
                  <input
                    id="resetEmail"
                    type="email"
                    className="ref-input"
                    style={{ paddingLeft: '1rem' }}
                    placeholder="name@example.com"
                    required
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="ref-modal-cancel"
                    onClick={() => setShowForgotModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="ref-primary-btn"
                    style={{ width: 'auto', padding: '0.6rem 1.25rem' }}
                    disabled={busy}
                  >
                    Send Reset Link
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Help Modal */}
      {showHelpModal && (
        <div className="ref-modal-backdrop" onClick={() => setShowHelpModal(false)}>
          <div className="ref-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ref-modal-header">
              <h3 className="ref-modal-title">Need Help?</h3>
              <button
                type="button"
                className="ref-modal-close"
                onClick={() => setShowHelpModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="ref-help-content">
              <h4>🩺 Patient / User Sign In</h4>
              <p>
                Patients and general users can sign in using their registered email and password, or
                via Google sign-in. Use the <strong>Create Account</strong> link if this is your
                first visit.
              </p>
              <h4>🛡️ Admin Access</h4>
              <p>
                Platform administrators must select the <strong>Admin</strong> tab. Admin accounts
                require a verified custom claim configured via backend CLI (<code>python promote_admin.py &lt;email&gt;</code>).
              </p>
              <h4>🔒 Privacy &amp; Security</h4>
              <p>
                All image uploads are classified in volatile RAM and discarded immediately. No raw retinal images are permanently saved to disk.
              </p>
            </div>
            <div style={{ textAlign: 'right', marginTop: '1.25rem' }}>
              <button
                type="button"
                className="ref-primary-btn"
                style={{ width: 'auto', padding: '0.6rem 1.25rem' }}
                onClick={() => setShowHelpModal(false)}
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Layout Specific Styles matching the reference format */}
      <style jsx>{`
        .ref-auth-page {
          min-height: 100vh;
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #eef4fb;
          padding: 2rem 1rem;
          font-family: inherit;
        }

        :global([data-theme='dark']) .ref-auth-page {
          background: #0f172a;
        }

        .ref-auth-container {
          width: 100%;
          max-width: 440px;
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .ref-back-link {
          align-self: flex-start;
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          color: #64748b;
          text-decoration: none;
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 1rem;
          transition: color 0.2s ease;
        }

        .ref-back-link:hover {
          color: #0b3b95;
        }

        :global([data-theme='dark']) .ref-back-link {
          color: #94a3b8;
        }

        :global([data-theme='dark']) .ref-back-link:hover {
          color: #60a5fa;
        }

        /* ── Main Card ── */
        .ref-auth-card {
          width: 100%;
          background: #ffffff;
          border-radius: 20px;
          box-shadow: 0 10px 30px -5px rgba(11, 59, 149, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
          padding: 2.25rem 2rem 1.75rem 2rem;
          border: 1px solid #e2e8f0;
          transition: box-shadow 0.2s ease;
        }

        :global([data-theme='dark']) .ref-auth-card {
          background: #1e293b;
          border-color: #334155;
          box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.4);
        }

        /* ── Header ── */
        .ref-header {
          text-align: center;
          margin-bottom: 1.5rem;
        }

        .ref-brand {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          text-decoration: none;
          margin-bottom: 0.25rem;
        }

        .ref-logo-icon {
          font-size: 1.75rem;
        }

        .ref-brand-name {
          font-size: 1.75rem;
          font-weight: 800;
          color: #0b3b95;
          letter-spacing: -0.02em;
        }

        :global([data-theme='dark']) .ref-brand-name {
          color: #60a5fa;
        }

        .ref-brand-accent {
          color: #2563eb;
        }

        :global([data-theme='dark']) .ref-brand-accent {
          color: #93c5fd;
        }

        .ref-subtitle {
          color: #64748b;
          font-size: 0.9rem;
          margin: 0;
          font-weight: 500;
        }

        :global([data-theme='dark']) .ref-subtitle {
          color: #94a3b8;
        }

        /* ── Segmented Role Tabs [ User | Admin ] ── */
        .ref-role-tabs {
          display: flex;
          background: #f1f5f9;
          border-radius: 10px;
          padding: 3px;
          margin-bottom: 1.5rem;
          border: 1px solid #e2e8f0;
        }

        :global([data-theme='dark']) .ref-role-tabs {
          background: #0f172a;
          border-color: #334155;
        }

        .ref-role-tab {
          flex: 1;
          padding: 0.55rem 1rem;
          border: none;
          background: transparent;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 600;
          color: #64748b;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        :global([data-theme='dark']) .ref-role-tab {
          color: #94a3b8;
        }

        .ref-role-tab.active {
          background: #ffffff;
          color: #0b3b95;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
        }

        :global([data-theme='dark']) .ref-role-tab.active {
          background: #1e293b;
          color: #60a5fa;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }

        .ref-config-alert {
          background: #fef2f2;
          color: #b91c1c;
          padding: 0.75rem;
          border-radius: 8px;
          font-size: 0.8rem;
          margin-bottom: 1rem;
          border: 1px solid #fecaca;
        }

        /* ── Form Inputs ── */
        .ref-form {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .ref-field {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
        }

        .ref-label {
          font-size: 0.875rem;
          font-weight: 600;
          color: #1e293b;
        }

        :global([data-theme='dark']) .ref-label {
          color: #e2e8f0;
        }

        .ref-input-wrap {
          position: relative;
          display: flex;
          align-items: center;
        }

        .ref-input-icon {
          position: absolute;
          left: 0.875rem;
          width: 18px;
          height: 18px;
          color: #94a3b8;
          display: flex;
          align-items: center;
          justify-content: center;
          pointer-events: none;
        }

        .ref-input-icon svg {
          width: 18px;
          height: 18px;
        }

        .ref-input {
          width: 100%;
          height: 46px;
          padding: 0 2.5rem 0 2.6rem;
          border: 1.5px solid #cbd5e1;
          border-radius: 10px;
          font-size: 0.95rem;
          color: #1e293b;
          background: #ffffff;
          transition: border-color 0.2s, box-shadow 0.2s;
        }

        :global([data-theme='dark']) .ref-input {
          background: #0f172a;
          border-color: #334155;
          color: #f1f5f9;
        }

        .ref-input:focus {
          outline: none;
          border-color: #0b3b95;
          box-shadow: 0 0 0 3px rgba(11, 59, 149, 0.12);
        }

        :global([data-theme='dark']) .ref-input:focus {
          border-color: #60a5fa;
          box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
        }

        .ref-input::placeholder {
          color: #94a3b8;
        }

        .ref-suffix-btn {
          position: absolute;
          right: 0.875rem;
          background: transparent;
          border: none;
          color: #94a3b8;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 20px;
          height: 20px;
        }

        .ref-suffix-btn svg {
          width: 18px;
          height: 18px;
        }

        .ref-suffix-btn:hover {
          color: #475569;
        }

        :global([data-theme='dark']) .ref-suffix-btn:hover {
          color: #cbd5e1;
        }

        /* ── Primary Sign In Button ── */
        .ref-primary-btn {
          width: 100%;
          height: 46px;
          background: #0b3b95;
          color: #ffffff;
          border: none;
          border-radius: 10px;
          font-size: 0.95rem;
          font-weight: 600;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          cursor: pointer;
          margin-top: 0.25rem;
          transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
          box-shadow: 0 4px 12px rgba(11, 59, 149, 0.2);
        }

        .ref-primary-btn:hover {
          background: #092c73;
          transform: translateY(-1px);
          box-shadow: 0 6px 16px rgba(11, 59, 149, 0.3);
        }

        .ref-primary-btn:disabled {
          opacity: 0.65;
          cursor: not-allowed;
          transform: none;
        }

        .ref-btn-icon {
          font-size: 1.1rem;
        }

        /* ── Divider ── */
        .ref-divider {
          display: flex;
          align-items: center;
          margin: 1.25rem 0;
          color: #94a3b8;
          font-size: 0.75rem;
          font-weight: 600;
          letter-spacing: 0.05em;
        }

        .ref-divider::before,
        .ref-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: #e2e8f0;
        }

        :global([data-theme='dark']) .ref-divider::before,
        :global([data-theme='dark']) .ref-divider::after {
          background: #334155;
        }

        .ref-divider span {
          padding: 0 0.85rem;
        }

        /* ── Google Button ── */
        .ref-google-btn {
          width: 100%;
          height: 46px;
          background: #ffffff;
          border: 1.5px solid #cbd5e1;
          border-radius: 10px;
          font-size: 0.95rem;
          font-weight: 600;
          color: #334155;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.75rem;
          cursor: pointer;
          transition: background 0.2s, border-color 0.2s;
        }

        :global([data-theme='dark']) .ref-google-btn {
          background: #0f172a;
          border-color: #334155;
          color: #e2e8f0;
        }

        .ref-google-btn:hover {
          background: #f8fafc;
          border-color: #94a3b8;
        }

        :global([data-theme='dark']) .ref-google-btn:hover {
          background: #1e293b;
        }

        .ref-google-icon {
          width: 20px;
          height: 20px;
        }

        /* ── Switch Link ── */
        .ref-switch-link {
          text-align: center;
          margin-top: 1.25rem;
          font-size: 0.875rem;
          color: #64748b;
        }

        :global([data-theme='dark']) .ref-switch-link {
          color: #94a3b8;
        }

        .ref-link-btn {
          background: none;
          border: none;
          color: #0b3b95;
          font-weight: 700;
          cursor: pointer;
          font-size: 0.875rem;
          padding: 0;
          text-decoration: none;
        }

        .ref-link-btn:hover {
          text-decoration: underline;
        }

        :global([data-theme='dark']) .ref-link-btn {
          color: #60a5fa;
        }

        /* ── Footer Links ── */
        .ref-card-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 1.25rem;
          margin-top: 1.25rem;
          border-top: 1px solid #f1f5f9;
        }

        :global([data-theme='dark']) .ref-card-footer {
          border-color: #334155;
        }

        .ref-footer-link {
          background: none;
          border: none;
          color: #0b3b95;
          font-size: 0.825rem;
          font-weight: 600;
          cursor: pointer;
          padding: 0;
          transition: opacity 0.2s;
        }

        :global([data-theme='dark']) .ref-footer-link {
          color: #60a5fa;
        }

        .ref-footer-link:hover {
          opacity: 0.8;
          text-decoration: underline;
        }

        .ref-help-link {
          color: #64748b;
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
        }

        :global([data-theme='dark']) .ref-help-link {
          color: #94a3b8;
        }

        /* ── Trust Badge ── */
        .ref-trust-badge {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.4rem;
          margin-top: 1.25rem;
          color: #10b981;
          font-size: 0.825rem;
          font-weight: 600;
        }

        .ref-trust-icon {
          width: 16px;
          height: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .ref-trust-icon svg {
          width: 16px;
          height: 16px;
        }

        /* ── Page Copyright ── */
        .ref-page-copyright {
          text-align: center;
          margin-top: 1.5rem;
          color: #64748b;
          font-size: 0.8rem;
        }

        :global([data-theme='dark']) .ref-page-copyright {
          color: #64748b;
        }

        /* ── Modals ── */
        .ref-modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.6);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 999;
          padding: 1rem;
        }

        .ref-modal {
          background: #ffffff;
          border-radius: 16px;
          padding: 1.75rem;
          width: 100%;
          max-width: 440px;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
        }

        :global([data-theme='dark']) .ref-modal {
          background: #1e293b;
          color: #f1f5f9;
        }

        .ref-modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .ref-modal-title {
          font-size: 1.25rem;
          font-weight: 700;
          margin: 0;
          color: #1e293b;
        }

        :global([data-theme='dark']) .ref-modal-title {
          color: #f1f5f9;
        }

        .ref-modal-close {
          background: none;
          border: none;
          font-size: 1.25rem;
          color: #94a3b8;
          cursor: pointer;
        }

        .ref-modal-desc {
          font-size: 0.9rem;
          color: #64748b;
          margin-bottom: 1.25rem;
          line-height: 1.5;
        }

        :global([data-theme='dark']) .ref-modal-desc {
          color: #94a3b8;
        }

        .ref-modal-success {
          background: #ecfdf5;
          color: #065f46;
          padding: 1rem;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 500;
          text-align: center;
        }

        .ref-modal-cancel {
          background: #f1f5f9;
          border: none;
          border-radius: 8px;
          padding: 0.6rem 1.25rem;
          font-weight: 600;
          color: #475569;
          cursor: pointer;
        }

        :global([data-theme='dark']) .ref-modal-cancel {
          background: #334155;
          color: #e2e8f0;
        }

        .ref-help-content h4 {
          font-size: 0.95rem;
          font-weight: 700;
          margin: 0.75rem 0 0.25rem 0;
          color: #0b3b95;
        }

        :global([data-theme='dark']) .ref-help-content h4 {
          color: #60a5fa;
        }

        .ref-help-content p {
          font-size: 0.85rem;
          color: #64748b;
          margin: 0 0 0.75rem 0;
          line-height: 1.45;
        }

        :global([data-theme='dark']) .ref-help-content p {
          color: #94a3b8;
        }
      `}</style>
    </div>
  );
}
