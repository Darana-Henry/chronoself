# ChronoSelf

Personal life-tracking dashboard hosted on Firebase. A collection of standalone HTML pages — no framework, no bundler, no runtime dependencies beyond Firebase.

## Architecture

**Pure static site.** Every page is a single self-contained HTML file with all CSS and JS inline. No npm packages at runtime. No build transpilation — the build step is only a string-replace for Firebase config injection.

**Hosting:** Firebase Hosting (`chronos-self.web.app`). The `dist/` folder is what gets deployed — never edit files there directly.

**Data persistence:**
- Primary: `localStorage` (keys prefixed `chrono_`)
- Optional cloud backup: Firestore under `users/{uid}/` — triggered manually via the "Sync to Firebase" button on the landing page
- Instagram follower history: `data/instagram.json` committed to the repo, served as a static asset at `/data/instagram.json`

## Build

```bash
node scripts/inject.js          # reads .env.qa, writes dist/
```

`inject.js` replaces `__PLACEHOLDER__` tokens in each HTML file with real Firebase config values and copies `data/` → `dist/data/`. Requires these env vars (in `.env.qa` locally, GitHub secrets in CI):

```
FIREBASE_API_KEY
FIREBASE_AUTH_DOMAIN
FIREBASE_PROJECT_ID
FIREBASE_STORAGE_BUCKET
FIREBASE_MESSAGING_SENDER_ID
FIREBASE_APP_ID
ALLOWED_EMAIL
```

Never commit `.env.qa` — it is gitignored.

## Deploy

```bash
node scripts/inject.js && firebase deploy --only hosting
```

## Pages

| File | URL | Purpose |
|------|-----|---------|
| `index.html` | `/` | Landing page — cards linking to every module |
| `schedule.html` | `/schedule.html` | Main app — Schedule, Tracker, Backlog, Goals, Freeletics, Chronicle, Classes, Instagram tabs |
| `portals.html` | `/portals.html` | Hub — cards linking to external projects (Ballpark, IPL, etc.) |
| `instagram.html` | `/instagram.html` | Standalone Instagram follower tracker page |

`schedule.html` reads `?tab=<name>` on load to deep-link into a specific tab. Valid tab names: `today`, `schedule`, `tracker`, `backlog`, `goals`, `freeletics`, `chronicle`, `classes`, `instagram`.

## Coding conventions

- **All CSS and JS inline** in the HTML file — no external `.css` or `.js` files
- **No chart libraries** — charts are drawn with vanilla SVG via `document.createElementNS`
- **No comments** unless the why is non-obvious
- **Dark theme** throughout: background `#0a0a0a`, text `#e8eaed`, grid overlay via `body::before`
- CSS custom properties defined at the top of `schedule.html`: `--txt`, `--txt-mid`, `--txt-dim`, `--line`, `--tab-h`
- Accent colours by feature: blue `#5b8eff` (schedule), green `#4ddd8e` (tracker), purple `#a06bff` (backlog), yellow `#ffc84d` (goals), orange `#ff8050` (freeletics), pink `#ff8fab` (chronicle), violet `#c97aff` (classes), violet `#c084fc` (Instagram)

## Instagram Tracker

Tracks follower counts for two public accounts daily:
- `hankcuratesfilms`
- `hanklosesweight`

**Automated collection:** `.github/workflows/instagram_tracker.yml` runs at 00:05 IST (18:35 UTC) daily.

Workflow steps:
1. `pip install instaloader==4.13.1` → run `scripts/fetch_instagram.py` → appends today's count to `data/instagram.json`
2. `node scripts/inject.js` → `firebase deploy --only hosting`
3. Commits the updated `data/instagram.json` back to `main`

**Data format** (`data/instagram.json`):
```json
{
  "hankcuratesfilms": [{"date": "2026-06-18", "count": 1234}],
  "hanklosesweight":  [{"date": "2026-06-18", "count": 567}]
}
```

**GitHub secrets required** (one-time setup):
- `FIREBASE_TOKEN` — from `firebase login:ci`
- All seven Firebase env vars listed above

**First run:** trigger manually via GitHub Actions → Actions → "Instagram Tracker" → Run workflow.
