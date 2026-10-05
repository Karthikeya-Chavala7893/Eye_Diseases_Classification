'use client';

/**
 * components/ThemeToggle.tsx
 * Dark/light switch backed by `useTheme` (localStorage + prefers-color-scheme).
 */

import { useTheme } from '@/hooks/useTheme';

/**
 * Render the theme toggle button.
 *
 * The icon spins briefly on activation, matching the legacy interaction.
 */
export function ThemeToggle(): JSX.Element {
  const { theme, toggleTheme, ready } = useTheme();

  return (
    <button
      type="button"
      className="theme-btn"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      aria-pressed={ready ? theme === 'dark' : undefined}
    >
      <span className="icon-sun" aria-hidden="true">☀️</span>
      <span className="icon-moon" aria-hidden="true">🌙</span>
    </button>
  );
}
