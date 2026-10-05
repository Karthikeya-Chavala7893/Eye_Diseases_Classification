'use client';

/**
 * hooks/useAuth.ts
 * Consume the authentication context.
 */

import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from '@/context/AuthContext';

/**
 * Access the current authentication state and credential operations.
 *
 * @returns The auth context value.
 * @throws Error when called outside `<AuthProvider>`.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth() must be used inside <AuthProvider>');
  }
  return context;
}
