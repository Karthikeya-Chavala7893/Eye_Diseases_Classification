'use client';

/**
 * components/LandingNav.tsx
 * Landing-page navigation with in-page anchor links.
 *
 * Uses IntersectionObserver to highlight the nav link whose section
 * is currently in view, so "Home" doesn't stay active when the user
 * scrolls to another section like "AI Screening".
 */

import { useEffect, useState } from 'react';

import { Navbar, type NavLink } from '@/components/Navbar';

const BASE_LINKS: Omit<NavLink, 'active'>[] = [
  { href: '/', label: 'Home' },
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How It Works' },
  { href: '#screening', label: 'AI Screening' },
  { href: '#awareness', label: 'Eye Health' },
];

/** Map each nav link to its corresponding section DOM id. */
const SECTION_IDS = ['home', 'features', 'how-it-works', 'screening', 'awareness'];

/** Render the landing-page navigation bar with scroll-aware active state. */
export function LandingNav(): JSX.Element {
  const [activeId, setActiveId] = useState<string>('home');

  useEffect(() => {
    const sections = SECTION_IDS
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: '-40% 0px -55% 0px', threshold: 0 },
    );

    for (const section of sections) {
      observer.observe(section);
    }

    return () => observer.disconnect();
  }, []);

  const links: NavLink[] = BASE_LINKS.map((link) => {
    const sectionId = link.href === '/' ? 'home' : link.href.replace('#', '');
    return { ...link, active: sectionId === activeId };
  });

  return <Navbar links={links} />;
}
