import { Suspense } from 'react';

import { AuthPanel } from '@/components/AuthPanel';

/**
 * app/login/page.tsx
 * ──────────────────
 * Authentication page shell.
 *
 * The static frame is server-rendered; the interactive `AuthPanel` (tabs, forms,
 * Firebase calls) is a Client Component wrapped in Suspense because it reads
 * search params.
 */

export const metadata = {
  title: 'Login',
  description: 'Secure sign-in for AI-powered eye health screening.',
};

/** Render the sign-in / registration page. */
export default function LoginPage(): JSX.Element {
  return (
    <div className="auth-page-root">
      <div className="auth-bg-pattern" aria-hidden="true" />
      <Suspense fallback={null}>
        <AuthPanel />
      </Suspense>
    </div>
  );
}
