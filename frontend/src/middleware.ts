/**
 * middleware.ts
 * ─────────────
 * Next.js Edge Middleware guarding the authenticated area.
 *
 * Redirects to /login when the `visionai-session` hint cookie (written by
 * AuthContext on sign-in) is absent, so unauthenticated visitors never see a
 * flash of the screening UI before React hydrates.
 *
 * This is a navigation-level UX guard, not the security boundary: every
 * privileged operation is authorised server-side by a verified Firebase JWT.
 */

import { NextResponse, type NextRequest } from 'next/server';

/** Session hint cookie written by the client after sign-in. */
const SESSION_COOKIE = 'visionai-session';

/**
 * Guard protected routes.
 *
 * @param request The incoming edge request.
 * @returns A redirect to the appropriate login page when unauthenticated, otherwise pass-through.
 */
export function middleware(request: NextRequest): NextResponse {
  if (request.cookies.get(SESSION_COOKIE)?.value) {
    return NextResponse.next();
  }

  const isAdminRoute = request.nextUrl.pathname.startsWith('/admin');
  const loginPath = isAdminRoute ? '/admin/login' : '/login';
  const loginUrl = new URL(loginPath, request.url);
  loginUrl.searchParams.set('next', request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = { matcher: ['/screening/:path*', '/admin/dashboard/:path*'] };
