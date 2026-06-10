from __future__ import annotations

import html
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _send(to: str, subject: str, html_body: str, text_body: str) -> None:
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")

    payload = {
        "from": settings.waitlist_from_email,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if settings.waitlist_reply_to:
        payload["reply_to"] = settings.waitlist_reply_to

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        logger.error("Resend error %s: %s", response.status_code, response.text)
        raise RuntimeError(f"Email delivery failed ({response.status_code})")


def _shell(inner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0c0c0e;font-family:Georgia,'Times New Roman',serif;color:#ece7dd;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0c0c0e;padding:40px 20px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:480px;">
        {inner}
        <tr><td style="padding-top:32px;font-family:ui-monospace,monospace;font-size:11px;color:rgba(236,231,221,0.35);letter-spacing:0.04em;">
          Engel · For iPhone · Coming soon
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_confirmation_email(to_email: str, confirm_url: str) -> None:
    safe_url = html.escape(confirm_url, quote=True)
    inner = f"""
        <tr><td style="font-size:28px;font-weight:300;letter-spacing:-0.02em;line-height:1.15;padding-bottom:16px;">
          Confirm early access
        </td></tr>
        <tr><td style="font-family:ui-monospace,monospace;font-size:14px;line-height:1.65;color:rgba(236,231,221,0.72);padding-bottom:28px;">
          You asked to hear when Engel opens. One click confirms your address.
          No spam. No motivation. Just a note when early access is ready.
        </td></tr>
        <tr><td style="padding-bottom:24px;">
          <a href="{safe_url}" style="display:inline-block;background:#ece7dd;color:#0c0c0e;font-family:ui-monospace,monospace;font-size:13px;font-weight:600;text-decoration:none;padding:14px 24px;border-radius:10px;">
            Confirm your email
          </a>
        </td></tr>
        <tr><td style="font-family:ui-monospace,monospace;font-size:12px;line-height:1.6;color:rgba(236,231,221,0.38);">
          Or copy this link:<br>
          <span style="word-break:break-all;color:rgba(236,231,221,0.55);">{safe_url}</span>
        </td></tr>
        <tr><td style="font-family:ui-monospace,monospace;font-size:11px;line-height:1.6;color:rgba(236,231,221,0.28);padding-top:24px;">
          If you did not request this, ignore this email.
        </td></tr>
    """
    text = (
        "Confirm early access to Engel\n\n"
        f"Confirm your email: {confirm_url}\n\n"
        "If you did not request this, ignore this email."
    )
    _send(to_email, "Confirm your early access — Engel", _shell(inner), text)


def send_welcome_email(to_email: str) -> None:
    inner = """
        <tr><td style="font-size:28px;font-weight:300;letter-spacing:-0.02em;line-height:1.15;padding-bottom:16px;">
          You're on the list.
        </td></tr>
        <tr><td style="font-family:ui-monospace,monospace;font-size:14px;line-height:1.65;color:rgba(236,231,221,0.72);padding-bottom:20px;">
          Your email is confirmed. When early access opens for iPhone, you'll hear from us.
        </td></tr>
        <tr><td style="font-family:ui-monospace,monospace;font-size:14px;line-height:1.65;color:rgba(236,231,221,0.55);">
          Notice what's repeating. Change one thing.
        </td></tr>
    """
    text = (
        "You're on the list.\n\n"
        "Your email is confirmed. When early access opens for iPhone, you'll hear from us.\n\n"
        "Notice what's repeating. Change one thing."
    )
    _send(to_email, "You're on the list — Engel", _shell(inner), text)
