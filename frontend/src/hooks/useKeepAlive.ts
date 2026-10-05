/**
 * hooks/useKeepAlive.ts
 * ─────────────────────
 * Periodically pings the backend /api/health endpoint to prevent Render's
 * free-tier "sleep on inactivity" from spinning down the server.
 *
 * Render free tier spins down after 15 minutes of inactivity. Cold starts
 * take 3-5 minutes (container boot + 138 MB model download + 3-model load).
 * This hook fires a lightweight GET every 10 minutes to keep the server warm.
 *
 * Usage:
 *   Call once in your root layout or _app — it self-manages via useEffect.
 */

'use client';

import { useEffect } from 'react';
import { API_BASE_URL } from '@/lib/api';

/** Interval between keep-alive pings (10 minutes). */
const PING_INTERVAL_MS = 10 * 60 * 1000;

/** How long to wait before the first ping after page load (30 seconds). */
const INITIAL_DELAY_MS = 30 * 1000;

/**
 * Keep the Render backend warm by polling /api/health every 10 minutes.
 * Stops automatically when the tab is hidden to avoid unnecessary wake-ups.
 */
export function useKeepAlive(): void {
  useEffect(() => {
    let timerId: ReturnType<typeof setTimeout>;

    const ping = async () => {
      // Don't ping if the tab is not visible (user switched tabs / minimised)
      if (document.visibilityState === 'hidden') return;

      try {
        await fetch(`${API_BASE_URL}/api/health`, {
          method: 'GET',
          // Short timeout — we just want to wake the server, not wait for model load
          signal: AbortSignal.timeout(5000),
        });
      } catch {
        // Silently ignore — network errors or a sleeping server are expected
      }

      // Schedule next ping
      timerId = setTimeout(ping, PING_INTERVAL_MS);
    };

    // Initial ping after a short delay so it doesn't compete with page load
    timerId = setTimeout(ping, INITIAL_DELAY_MS);

    return () => clearTimeout(timerId);
  }, []);
}
