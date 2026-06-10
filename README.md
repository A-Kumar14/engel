# Engel

A reflective iOS journal built around two mirrored spaces: a **green globe** for energy, wins, and aliveness, and a **red globe** for friction, heaviness, and feeling stuck. Capture fragments by voice or text, let AI suggest sorting and tags, and notice patterns weekly. No scoring, no streaks, no advice — just your thoughts, kept visible and always yours.

> **Landing page:** [a-kumar14.github.io/engel](https://a-kumar14.github.io/engel)
## What's in this repo

This is the public repository for Engel. It bundles three things:

| Path | What it is | Deploy target |
|------|------------|---------------|
| `docs/` | Marketing landing page + waitlist | GitHub Pages |
| `engel/` | iOS app (SwiftUI) + FastAPI backend | App Store / Render |
| `render.yaml` | Backend + Postgres service definition | [Render](https://render.com) |

## Components

### Landing page (`docs/`)

Static site served from GitHub Pages. Holds the marketing page, screenshots, and the email waitlist form. Posts to the backend's waitlist endpoint and redirects to a confirmation page on success.

### iOS app (`engel/`)

SwiftUI app, iOS 17+. Two globes on a simple home, voice/text capture, AI-assisted sorting, and weekly insights. Talks to the FastAPI backend. See [engel/README.md](engel/README.md) for app-specific setup.

### Backend (`engel/backend/`)

FastAPI + SQLAlchemy. Serves entry storage, AI sorting, weekly insight generation, and the waitlist. SQLite for local dev, Postgres in production.

## Getting started

### iOS app

```bash
cd engel
xed .          # open in Xcode
# or build from CLI
xcodebuild -scheme engel -destination 'platform=iOS Simulator,name=iPhone 16' build
```

### Backend

```bash
cd engel/backend
cp ../.env.example .env     # fill in API keys
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`. Health check: `/api/health`.

### Landing page

Open `docs/index.html` directly, or serve the `docs/` folder:

```bash
python -m http.server -d docs 8080
```

## Deployment

- **Landing page** → GitHub Pages, served from `docs/` at `a-kumar14.github.io/engel`.
- **Backend + database** → Render, defined in `render.yaml` (web service + free Postgres). Set `RESEND_API_KEY`, `WAITLIST_FROM_EMAIL`, and `PUBLIC_API_BASE_URL` as secrets in the Render dashboard.

## Design principles

- Never prescribe, diagnose, or moralize
- Show at most one insight per week
- Skip is always a valid option
- Export is one tap
- No streaks, no guilt loops
- Authority stays with the human; AI suggestions are always editable

## Tech stack

- **iOS** — SwiftUI, SwiftData, iOS 17+
- **Backend** — Python, FastAPI, SQLAlchemy; SQLite (dev) / Postgres (prod)
- **AI** — Anthropic Claude (sorting), OpenAI Whisper (transcription)
- **Email** — Resend (waitlist)
- **Fonts** — Fraunces (display), JetBrains Mono (UI)

## License

Private — all rights reserved.
