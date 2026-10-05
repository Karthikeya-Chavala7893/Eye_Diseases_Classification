'use client';

/**
 * context/AuthContext.tsx
 * ───────────────────────
 * Single source of truth for client-side authentication state.
 *
 * Wraps Firebase's `onAuthStateChanged` in React context so every component
 * sees the same `{ user, loading, error }` triple. All credential operations
 * happen here through the Firebase JS SDK — they are deliberately NOT proxied
 * through Flask (constraint #17).
 *
 * A short-lived `visionai-session` cookie mirrors the sign-in state so Next.js
 * Edge Middleware can guard `/screening` before React hydrates, preventing a
 * flash of unauthenticated content. The cookie is a UX hint only — every
 * privileged action is still authorised by a verified Bearer token server-side.
 */

import {
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  type User,
} from 'firebase/auth';
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { syncUser } from '@/lib/api';
import { getFirebaseAuth, googleProvider, isFirebaseConfigured } from '@/lib/firebase';

/** Name of the middleware-visible session hint cookie. */
export const SESSION_COOKIE = 'visionai-session';

/** Everything `useAuth()` exposes to consumers. */
export interface AuthContextValue {
  user: User | null;
  /** True until the first `onAuthStateChanged` callback resolves. */
  loading: boolean;
  /** Last auth error message, or null. */
  error: string | null;
  /** True when the `NEXT_PUBLIC_FIREBASE_*` variables are present. */
  configured: boolean;
  /** True when the signed-in user has the `admin` custom claim. */
  isAdmin: boolean;
  registerWithEmail: (name: string, email: string, password: string) => Promise<User>;
  signInWithEmail: (email: string, password: string) => Promise<User>;
  signInWithGoogle: () => Promise<User>;
  resetPassword: (email: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Write or clear the middleware session hint.
 *
 * 7-day max-age matches Firebase's default token persistence so the cookie
 * never expires while the user is genuinely signed in. The cookie is also
 * refreshed on every onAuthStateChanged tick so long sessions stay alive.
 */
function setSessionCookie(active: boolean): void {
  if (typeof document === 'undefined') return;
  document.cookie = active
    ? `${SESSION_COOKIE}=1; path=/; max-age=${7 * 24 * 3600}; SameSite=Lax`
    : `${SESSION_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

/** Translate a Firebase error code into a message a patient can act on. */
function friendlyAuthError(cause: unknown): string {
  const code = typeof cause === 'object' && cause !== null && 'code' in cause
    ? String((cause as { code: unknown }).code)
    : '';

  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
      return 'Invalid email or password';
    case 'auth/email-already-in-use':
      return 'Email already registered. Try signing in instead.';
    case 'auth/weak-password':
      return 'Password must be at least 8 characters';
    case 'auth/invalid-email':
      return 'Please enter a valid email address';
    case 'auth/too-many-requests':
      return 'Too many attempts. Please wait a moment and try again.';
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return 'Google sign-in was cancelled';
    case 'auth/operation-not-allowed':
      return 'This sign-in method is disabled in the Firebase console';
    case 'auth/network-request-failed':
      return 'Network error. Check your connection and try again.';
    default:
      return cause instanceof Error && cause.message
        ? cause.message
        : 'Authentication failed. Please try again.';
  }
}

/**
 * Provide authentication state to the whole app.
 *
 * @param children The subtree that consumes `useAuth()`.
 */
export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      setError(
        'Firebase is not configured. Copy frontend/.env.example to frontend/.env.local and ' +
          'fill in the NEXT_PUBLIC_FIREBASE_* values.',
      );
      return;
    }

    const unsubscribe = onAuthStateChanged(getFirebaseAuth(), async (nextUser) => {
      setUser(nextUser);
      // Refresh the cookie on every state change so a long-lived Firebase
      // session never gets blocked by an expired middleware cookie.
      setSessionCookie(Boolean(nextUser));

      // Read the admin custom claim from the cached token for instant navigation.
      if (nextUser) {
        try {
          const tokenResult = await nextUser.getIdTokenResult(false);
          setIsAdmin(Boolean(tokenResult.claims.admin));
        } catch {
          setIsAdmin(false);
        }
      } else {
        setIsAdmin(false);
      }

      setLoading(false);
    });
    return unsubscribe;
  }, []);

  /** Mirror the signed-in profile into Firestore; failure must not block login. */
  const syncProfile = useCallback(async (nextUser: User): Promise<void> => {
    try {
      await syncUser(nextUser);
    } catch {
      // The backend may be down; the session is still perfectly usable.
    }
  }, []);

  const registerWithEmail = useCallback(
    async (name: string, email: string, password: string): Promise<User> => {
      setError(null);
      try {
        const credential = await createUserWithEmailAndPassword(getFirebaseAuth(), email, password);
        await updateProfile(credential.user, { displayName: name });
        await credential.user.reload();
        const currentUser = getFirebaseAuth().currentUser ?? credential.user;
        setUser(currentUser);
        setSessionCookie(true);
        await syncProfile(currentUser);
        return currentUser;
      } catch (cause) {
        const message = friendlyAuthError(cause);
        setError(message);
        throw new Error(message);
      }
    },
    [syncProfile],
  );

  const signInWithEmail = useCallback(
    async (email: string, password: string): Promise<User> => {
      setError(null);
      try {
        const credential = await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
        setUser(credential.user);
        setSessionCookie(true);
        await syncProfile(credential.user);
        return credential.user;
      } catch (cause) {
        const message = friendlyAuthError(cause);
        setError(message);
        throw new Error(message);
      }
    },
    [syncProfile],
  );

  const signInWithGoogle = useCallback(async (): Promise<User> => {
    setError(null);
    try {
      const provider: GoogleAuthProvider = googleProvider();
      const credential = await signInWithPopup(getFirebaseAuth(), provider);
      setUser(credential.user);
      setSessionCookie(true);
      await syncProfile(credential.user);
      return credential.user;
    } catch (cause) {
      const message = friendlyAuthError(cause);
      setError(message);
      throw new Error(message);
    }
  }, [syncProfile]);

  const resetPassword = useCallback(async (email: string): Promise<void> => {
    setError(null);
    try {
      await sendPasswordResetEmail(getFirebaseAuth(), email);
    } catch (cause) {
      const message = friendlyAuthError(cause);
      setError(message);
      throw new Error(message);
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    await signOut(getFirebaseAuth());
    setSessionCookie(false);
  }, []);

  const clearError = useCallback((): void => setError(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      error,
      configured: isFirebaseConfigured,
      isAdmin,
      registerWithEmail,
      signInWithEmail,
      signInWithGoogle,
      resetPassword,
      logout,
      clearError,
    }),
    [user, loading, error, isAdmin, registerWithEmail, signInWithEmail, signInWithGoogle, resetPassword, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
