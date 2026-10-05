'use client';

/**
 * hooks/useTheme.ts
 * Dark/light theme state with localStorage persistence.
 *
 * Precedence: an explicit stored choice wins; otherwise the OS
 * `prefers-color-scheme` setting is followed live.
 */

import { useCallback, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

/** localStorage key holding the user's explicit choice. */
export const THEME_STORAGE_KEY = 'theme';

interface UseThemeResult {
  theme: Theme;
  toggleTheme: () => void;
  /** False until the stored preference has been read on the client. */
  ready: boolean;
}

/** Apply a theme to the document root so CSS custom properties switch. */
function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
}

/**
 * Read, apply and persist the colour theme.
 *
 * @returns The active theme, a toggle function, and a hydration flag.
 */
export function useTheme(): UseThemeResult {
  const [theme, setTheme] = useState<Theme>('light');
  const [ready, setReady] = useState<boolean>(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const initial: Theme = stored === 'dark' || stored === 'light'
      ? stored
      : media.matches ? 'dark' : 'light';

    setTheme(initial);
    applyTheme(initial);
    setReady(true);

    const onSystemChange = (event: MediaQueryListEvent): void => {
      if (window.localStorage.getItem(THEME_STORAGE_KEY)) return;
      const next: Theme = event.matches ? 'dark' : 'light';
      setTheme(next);
      applyTheme(next);
    };
    media.addEventListener('change', onSystemChange);
    return () => media.removeEventListener('change', onSystemChange);
  }, []);

  const toggleTheme = useCallback((): void => {
    setTheme((current) => {
      const next: Theme = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { theme, toggleTheme, ready };
}
