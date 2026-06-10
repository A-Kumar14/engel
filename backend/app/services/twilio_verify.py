import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


DEV_FALLBACK_CODE = "000000"


def _twilio_configured() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_verify_service_sid)


def start_sms_verification(phone_e164: str) -> str | None:
    """
    Starts an SMS verification via Twilio Verify.

    Returns:
      - None in production mode (no code ever returned to client)
      - A debug code in dev when Twilio isn't configured
    """
    if not _twilio_configured():
        if settings.env.lower() == "dev":
            logger.warning("Twilio not configured; using DEV fallback code for %s", phone_e164)
            return DEV_FALLBACK_CODE
        raise RuntimeError("Twilio Verify is not configured")

    from twilio.rest import Client  # imported lazily so dev installs aren't required for non-2FA paths

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.verify.v2.services(settings.twilio_verify_service_sid).verifications.create(
        to=phone_e164,
        channel="sms",
    )
    return None


def check_sms_verification(phone_e164: str, code: str) -> bool:
    if not _twilio_configured():
        if settings.env.lower() == "dev":
            return code == DEV_FALLBACK_CODE
        raise RuntimeError("Twilio Verify is not configured")

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    check = client.verify.v2.services(settings.twilio_verify_service_sid).verification_checks.create(
        to=phone_e164,
        code=code,
    )
    return (check.status or "").lower() == "approved"

