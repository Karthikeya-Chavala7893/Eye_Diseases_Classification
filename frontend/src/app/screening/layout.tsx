/**
 * app/screening/layout.tsx
 * Protected area shell.
 *
 * The route is dynamic: results are personal, so nothing here may be cached or
 * statically generated. Edge Middleware (src/middleware.ts) already redirects
 * unauthenticated visitors to /login before this renders.
 */

import type { ReactNode } from 'react';

export const metadata = {
  title: 'Eye Screening',
  description: 'AI-powered eye disease screening and analysis.',
};

export const dynamic = 'force-dynamic';

/** Wrap the screening route. */
export default function ScreeningLayout({ children }: { children: ReactNode }): JSX.Element {
  return <>{children}</>;
}
