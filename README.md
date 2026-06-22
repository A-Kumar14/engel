# Engel

A reflective iOS journal built around two mirrored spaces: a **green globe** for energy, wins, and aliveness, and a **red globe** for friction, heaviness, and feeling stuck. Capture fragments by voice or text, let AI suggest sorting and tags, and notice patterns weekly. No scoring, no streaks, no advice — just your thoughts, kept visible and always yours.

> **Landing page:** [a-kumar14.github.io/engel](https://a-kumar14.github.io/engel)
## What's in this repo

This is the public repository for Engel. It bundles three things:

| Path | What it is | Deploy target |
|------|------------|---------------|
| `index.html` | Marketing landing page + waitlist | GitHub Pages |
| `backend/` | FastAPI backend | Railway |
| `backend/railway.toml` | Backend service definition | [Railway](https://railway.com) |

## Components

### Landing page

Static site at repo root (`index.html`), served on GitHub Pages.

### Backend (`backend/`)

FastAPI + SQLAlchemy. Serves entry storage, AI sorting, weekly insight generation, and the waitlist. SQLite for local dev, Postgres in production.

## Getting started

### Backend

```bash
cd backend
cp .env.example .env     # fill in API keys
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`. Health check: `/api/health`.

### Landing page

Open `index.html` directly, or serve the repo root:

```bash
python -m http.server 8080
```

## Deployment

- **Landing page** → GitHub Pages at `a-kumar14.github.io/engel` (`index.html`, `confirmed.html`).
- **Backend + database** → Railway (`backend/railway.toml`). Add a Postgres plugin and set secrets in the Railway dashboard.

See [DEPLOYMENT.md](DEPLOYMENT.md) for env vars, data migration from Render, and cutover steps.

Required Railway secrets: `RESEND_API_KEY`, `WAITLIST_FROM_EMAIL`, `PUBLIC_API_BASE_URL`, and `DATABASE_URL` (from Postgres plugin).

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
