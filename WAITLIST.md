# Waitlist — email confirmation setup

The landing page uses **double opt-in**: users receive a confirmation email, click the link, then receive a welcome email.

## Flow

1. User submits email on [a-kumar14.github.io/engel](https://a-kumar14.github.io/engel/)
2. API sends **Confirm your early access — Engel** via [Resend](https://resend.com)
3. User clicks link → `GET /api/waitlist/confirm/{token}` → redirects to `confirmed.html`
4. API sends **You're on the list — Engel**

## Deploy the API (Render)

1. Push this repo to GitHub (includes `render.yaml` + `backend/`)
2. [Render Dashboard](https://dashboard.render.com) → **New Blueprint** → connect `A-Kumar14/engel`
3. Set secret env vars:
   - `RESEND_API_KEY` — from Resend dashboard
   - `WAITLIST_FROM_EMAIL` — verified sender, e.g. `Engel <hello@yourdomain.com>`
   - `PUBLIC_API_BASE_URL` — your Render URL, e.g. `https://engel-api.onrender.com`
4. Wait for deploy; hit `https://engel-api.onrender.com/api/health`

## Resend

1. Create account at [resend.com](https://resend.com)
2. Add and verify your domain (required to email any address)
3. Or use `onboarding@resend.dev` for testing (Resend account email only)
4. Create API key → paste into Render as `RESEND_API_KEY`

## Local test

```bash
cd backend
cp .env.example .env   # fill RESEND_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Serve the landing page locally and set in `config.js`:

```js
window.ENGEL_CONFIG = { API_BASE: "http://127.0.0.1:8000" };
```

```bash
cd docs && python3 -m http.server 8080
```

Open http://127.0.0.1:8080 — submit your email — check inbox.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/waitlist/subscribe` | `{ "email": "..." }` → sends confirmation |
| GET | `/api/waitlist/confirm/{token}` | Confirms + sends welcome email + redirect |

## Landing page config

`docs/config.js` — set `API_BASE` to your deployed Render URL (already `https://engel-api.onrender.com` by default).
