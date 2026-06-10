# Backend

FastAPI service for the Engel app.

## Scope
- entry capture records
- green/red sorting state
- pointer tagging
- weekly insight surfacing
- no export functionality

## Run
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

## Default Storage
- SQLite for local development via `backend/engel.db`
- swap `DATABASE_URL` later for Postgres in production
