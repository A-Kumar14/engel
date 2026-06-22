# Engel — Deployment

Split hosting: **GitHub Pages** (landing) + **Railway** (API + Postgres).

## Railway project

```
engel (Railway project)
├── engel-api     (web service, root: backend)
└── Postgres      (plugin)
```

| Setting | Value |
|---------|-------|
| Root directory | `backend` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/api/health` |
| Config file | `backend/railway.toml` |

### Required variables

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Reference from Railway Postgres plugin |
| `CORS_ORIGINS` | `https://a-kumar14.github.io,http://127.0.0.1:8080,http://localhost:8080` |
| `WAITLIST_SUCCESS_URL` | `https://a-kumar14.github.io/engel/confirmed.html` |
| `PUBLIC_API_BASE_URL` | `https://<engel-api>.up.railway.app` (no trailing slash) |
| `RESEND_API_KEY` | From Resend dashboard |
| `WAITLIST_FROM_EMAIL` | Verified Resend sender |
| `ENV` | `prod` |

### Optional (iOS AI features)

`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

## GitHub Pages (landing)

Repo root is served at `https://a-kumar14.github.io/engel` (`index.html`, `confirmed.html`).

Waitlist form should `POST` to `{PUBLIC_API_BASE_URL}/api/waitlist/subscribe`.

## Migrate data from Render (if needed)

```bash
pg_dump "$RENDER_DATABASE_URL" --no-owner --no-acl -f engel_backup.sql
psql "$RAILWAY_DATABASE_URL" -f engel_backup.sql
```

## Verification

```bash
curl -s https://<engel-api>.up.railway.app/api/health
```

## Decommission Render

After 48h on Railway: delete `engel-api` web service and `engel-db` on Render.
