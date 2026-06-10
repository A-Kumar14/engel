from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.waitlist import router as waitlist_router
from app.core.config import settings
from app.db import Base, engine


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Engel Backend",
    version="0.1.0",
    summary="API for entries, pointers, and weekly insights.",
)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(router)
app.include_router(waitlist_router)
