/**
 * VisionAI — app.js
 * Shared utilities loaded on every page:
 *   - CSRF token helper
 *   - Navigation (smooth scroll, active link, mobile toggle)
 *   - Theme toggle (dark / light mode)
 *   - Utility helpers: cap(), darken()
 */

// ═══════════════════════════════════════════════════════════════════════════════
// CSRF TOKEN HELPER
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Retrieves the CSRF token from the meta tag injected by Flask-WTF.
 * Returns an empty string if the meta tag is not present.
 */
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

// ═══════════════════════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════

function initNavigation() {
    // Smooth scroll for nav links
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                const offset = 80;
                const pos = target.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({ top: pos, behavior: 'smooth' });
            }
        });
    });

    // Active nav link on scroll
    const sections = document.querySelectorAll('section[id]');
    window.addEventListener('scroll', () => {
        const scrollPos = window.scrollY + 100;
        sections.forEach(section => {
            const top = section.offsetTop;
            const height = section.offsetHeight;
            const id = section.getAttribute('id');
            const link = document.querySelector(`.nav-link[href="#${id}"]`);
            if (link) {
                link.classList.toggle('active', scrollPos >= top && scrollPos < top + height);
            }
        });

        // Navbar background on scroll
        const navbar = document.getElementById('navbar');
        if (navbar) {
            navbar.style.boxShadow = window.scrollY > 50 ? 'var(--shadow-md)' : 'none';
        }
    });

    // Mobile menu toggle
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');
    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════════════════════════

function initTheme() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;

    const saved = localStorage.getItem('theme');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved) document.documentElement.setAttribute('data-theme', saved);
    else if (sysDark) document.documentElement.setAttribute('data-theme', 'dark');

    btn.addEventListener('click', () => {
        const curr = document.documentElement.getAttribute('data-theme');
        const next = curr === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        btn.style.transform = 'scale(1.1) rotate(180deg)';
        setTimeout(() => btn.style.transform = '', 300);
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════

/** Capitalise first character of a string. */
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

/** Darken a hex colour by `pct` percent (positive = darker). */
function darken(hex, pct) {
    const n = parseInt(hex.replace('#', ''), 16);
    const a = Math.round(2.55 * -pct);
    const R = Math.max(0, Math.min(255, (n >> 16) + a));
    const G = Math.max(0, Math.min(255, (n >> 8 & 0xFF) + a));
    const B = Math.max(0, Math.min(255, (n & 0xFF) + a));
    return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// BOOT — runs on every page that loads app.js
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initTheme();
});
