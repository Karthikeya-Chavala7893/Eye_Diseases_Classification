# `legacy/` — the pre-v2.0 Flask monolith (archived, not running)

Nothing in this directory is imported, served or executed by the current
application. It is kept only as a reference for the v2.0 restructuring and can
be deleted at any time.

## What is here

| Path | What it was |
|---|---|
| `app.py` | The original 497-line monolith: Flask routes + Jinja2 SSR + Flask-Login sessions + Authlib Google OAuth + Werkzeug password hashing + Firestore access + AI inference, all in one module. |
| `templates/` | Jinja2 templates (`base.html`, `index.html`, `login.html`, `screening.html`). |
| `static/` | `style.css` (42 KB design system), `script.js` (the pre-modular bundle) and `js/` (`app.js`, `diseases.js`, `screening.js`, `report.js`). |
| `tests/` | The 24-test pytest suite written against the monolith. |
| `pytest.ini` | Pytest config for that suite. |
| `requirements.txt` | Dependency set including Flask-Login, Flask-WTF and Authlib. |
| `.env.example` | The single-tier environment template. |

## Where each piece lives now

| Legacy | Replacement |
|---|---|
| `app.py` (routes) | `backend/app.py` — JSON-only REST API under `/api/` |
| `app.py` (Config + validate_config) | `backend/config.py` |
| `app.py` (model load + inference) | `backend/model.py` |
| `app.py` (Firestore CRUD) | `backend/db.py` |
| `app.py` (Flask-Login + Authlib) | `backend/auth.py` (Firebase JWT) + Firebase Auth in the browser |
| `templates/index.html` | `frontend/src/app/page.tsx` |
| `templates/login.html` | `frontend/src/app/login/page.tsx` + `frontend/src/components/AuthPanel.tsx` |
| `templates/screening.html` | `frontend/src/app/screening/page.tsx` |
| `static/style.css` + template `<style>` blocks | `frontend/src/app/globals.css` |
| `static/js/diseases.js` | `frontend/src/lib/diseases.ts` |
| `static/js/report.js` | `frontend/src/lib/pdf.ts` |
| `static/js/screening.js` | `frontend/src/hooks/usePrediction.ts` + screening page + components |
| `static/js/app.js` | `frontend/src/hooks/useTheme.ts` + `components/Navbar.tsx` |
| `tests/` | `backend/tests/` (98 tests) |

## Removing it

```bash
git rm -r legacy
```
