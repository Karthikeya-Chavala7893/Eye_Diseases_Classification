'use client';

/**
 * components/Navbar.tsx
 * ─────────────────────
 * Auth-aware top navigation, ported from the shared header in
 * templates/index.html and templates/screening.html.
 *
 * Signed out -> "Sign In" call to action.
 * Signed in  -> avatar dropdown with the profile summary and sign-out.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { useAuth } from '@/hooks/useAuth';

/** One entry in the primary navigation. */
export interface NavLink {
  href: string;
  label: string;
  /** Marks the entry that represents the current page. */
  active?: boolean;
}

/**
 * Render the site navigation bar.
 *
 * @param links Primary navigation entries for the current page.
 */
export function Navbar({ links }: { links: NavLink[] }): JSX.Element {
  const { user, logout, isAdmin } = useAuth();
  const router = useRouter();

  const [menuOpen, setMenuOpen] = useState<boolean>(false);
  const [dropdownOpen, setDropdownOpen] = useState<boolean>(false);
  const [scrolled, setScrolled] = useState<boolean>(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onScroll = (): void => setScrolled(window.scrollY > 50);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent): void => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, []);

  const displayName = user?.displayName ?? user?.email?.split('@')[0] ?? 'User';
  const initial = displayName.charAt(0).toUpperCase();

  const handleSignOut = async (): Promise<void> => {
    setDropdownOpen(false);
    await logout();
    router.push('/');
  };

  return (
    <nav className="navbar" id="navbar" style={{ boxShadow: scrolled ? 'var(--shadow-md)' : 'none' }}>
      <div className="nav-container">
        <Link href="/" className="nav-logo">
          <span className="logo-icon" aria-hidden="true">👁️</span>
          <span className="logo-text">
            Vision<span className="logo-accent">AI</span>
          </span>
        </Link>

        <div className={`nav-links${menuOpen ? ' active' : ''}`} id="navLinks">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link${link.active ? ' active' : ''}`}
              aria-current={link.active ? 'page' : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="nav-actions">
          <ThemeToggle />

          {user ? (
            <div className="user-menu" ref={menuRef}>
              <button
                type="button"
                className="user-btn"
                onClick={() => setDropdownOpen((open) => !open)}
                aria-expanded={dropdownOpen}
                aria-haspopup="menu"
                aria-label="Account menu"
              >
                <span className="user-avatar" aria-hidden="true">{initial}</span>
                <span className="user-name">{displayName}</span>
                <span className="dropdown-arrow" aria-hidden="true">▼</span>
              </button>

              <div className={`user-dropdown${dropdownOpen ? ' show' : ''}`} role="menu">
                <div className="dropdown-header">
                  <span className="dropdown-name">{displayName}</span>
                  <span className="dropdown-email">{user.email}</span>
                </div>
                <div className="dropdown-divider" />
                {isAdmin && (
                  <Link href="/admin/dashboard" className="dropdown-item" role="menuitem" onClick={() => setDropdownOpen(false)}>
                    <span aria-hidden="true">🛡️</span>
                    <span>Admin Panel</span>
                  </Link>
                )}
                <Link href="/screening" className="dropdown-item" role="menuitem" onClick={() => setDropdownOpen(false)}>
                  <span aria-hidden="true">👁️</span>
                  <span>AI Screening</span>
                </Link>
                <button type="button" className="dropdown-item logout-item" role="menuitem" onClick={handleSignOut}>
                  <span aria-hidden="true">🚪</span>
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          ) : (
            <Link href="/login" className="nav-cta">
              Sign In
            </Link>
          )}
        </div>

        <button
          type="button"
          className="nav-toggle"
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-label="Toggle navigation menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>
    </nav>
  );
}
