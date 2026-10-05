'use client';

/**
 * components/KeepAlive.tsx
 * ────────────────────────
 * Client-only component that runs the backend keep-alive ping loop.
 * Rendered inside the root layout so it's always active regardless of route.
 */

import { useKeepAlive } from '@/hooks/useKeepAlive';

/**
 * Invisible client component. Mounts the keep-alive hook once per page load.
 * Prevents Render's free-tier 15-minute inactivity sleep.
 */
export function KeepAlive(): null {
  useKeepAlive();
  return null;
}
