import { Suspense } from 'react';

import { AdminLoginPanel } from '@/components/AdminLoginPanel';

/**
 * app/admin/login/page.tsx
 * ───────────────────────
 * Admin authentication page shell.
 *
 * The static frame is server-rendered; the interactive `AdminLoginPanel`
 * is a Client Component wrapped in Suspense because it reads search params.
 */

export const metadata = {
  title: 'Admin Login',
  description: 'Secure admin sign-in for VisionAI platform management.',
};

export default function AdminLoginPage(): JSX.Element {
  return (
    <div className="auth-page-root">
      <div className="auth-bg-pattern" aria-hidden="true" />
      <Suspense fallback={null}>
        <AdminLoginPanel />
      </Suspense>
    </div>
  );
}
