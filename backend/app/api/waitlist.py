from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import WaitlistSubscriber
from app.schemas import WaitlistSubscribeRequest, WaitlistSubscribeResponse
from app.services.waitlist_email import send_confirmation_email, send_welcome_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{settings.api_prefix}/waitlist", tags=["waitlist"])

# Simple in-memory rate limit: IP -> list of request timestamps
_RATE: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW_SEC = 3600
_RATE_MAX = 8


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _check_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    window_start = now - _RATE_WINDOW_SEC
    _RATE[ip] = [t for t in _RATE[ip] if t > window_start]
    if len(_RATE[ip]) >= _RATE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
        )
    _RATE[ip].append(now)


def _confirm_url(token: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}{settings.api_prefix}/waitlist/confirm/{token}"


@router.post("/subscribe", response_model=WaitlistSubscribeResponse)
def subscribe(
    payload: WaitlistSubscribeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WaitlistSubscribeResponse:
    if not settings.resend_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Waitlist email is not configured yet.",
        )

    _check_rate_limit(request)
    email = payload.email.strip().lower()

    existing = db.query(WaitlistSubscriber).filter(WaitlistSubscriber.email == email).first()

    if existing and existing.confirmed_at is not None:
        return WaitlistSubscribeResponse(
            status="already_confirmed",
            message="You're already on the list.",
        )

    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()

    if existing:
        existing.confirm_token = token
        existing.confirmation_sent_at = now
        subscriber = existing
    else:
        subscriber = WaitlistSubscriber(
            email=email,
            confirm_token=token,
            confirmation_sent_at=now,
        )
        db.add(subscriber)

    try:
        send_confirmation_email(email, _confirm_url(token))
    except Exception:
        logger.exception("Failed to send confirmation email to %s", email)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send confirmation email. Try again in a few minutes.",
        )

    db.commit()
    db.refresh(subscriber)

    return WaitlistSubscribeResponse(
        status="confirmation_sent",
        message="Check your inbox to confirm your email.",
    )


@router.get("/confirm/{token}")
def confirm(token: str, db: Session = Depends(get_db)) -> RedirectResponse:
    subscriber = (
        db.query(WaitlistSubscriber)
        .filter(WaitlistSubscriber.confirm_token == token)
        .first()
    )

    error_url = f"{settings.waitlist_success_url}?error=invalid"
    success_url = f"{settings.waitlist_success_url}?confirmed=1"

    if subscriber is None:
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    # Expire confirmation links after 48 hours
    if subscriber.confirmation_sent_at is not None:
        age = datetime.utcnow() - subscriber.confirmation_sent_at
        if age > timedelta(hours=48):
            return RedirectResponse(url=f"{settings.waitlist_success_url}?error=expired", status_code=status.HTTP_302_FOUND)

    if subscriber.confirmed_at is not None:
        return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)

    subscriber.confirmed_at = datetime.utcnow()
    subscriber.confirm_token = None
    db.add(subscriber)
    db.commit()

    try:
        send_welcome_email(subscriber.email)
    except Exception:
        logger.exception("Failed to send welcome email to %s", subscriber.email)
        # Confirmation still counts — user is on the list
        return RedirectResponse(
            url=f"{settings.waitlist_success_url}?confirmed=1&welcome=pending",
            status_code=status.HTTP_302_FOUND,
        )

    return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)
