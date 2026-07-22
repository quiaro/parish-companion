import asyncio
import json
import logging
import smtplib
from email.message import EmailMessage

from config import settings
from translations import get_string

logger = logging.getLogger(__name__)


async def send_crisis_notification(telegram_user_id: int, language: str = "en") -> bool:
    """
    Urgent, staff-facing alert for a /comfort message flagged as a possible crisis
    (self-harm, suicidal ideation, sexual abuse, or physical violence). Reuses the same
    SMTP settings and recipient list as /contact, but isn't a ContactRequest — this is a
    system-triggered alert, not a parishioner-submitted intake form. Localized to the
    parishioner's session language, matching /contact's email convention.
    """
    subject = get_string("comfort_crisis_email_subject", language)
    body = get_string("comfort_crisis_email_body", language).format(telegram_user_id=telegram_user_id)
    return await asyncio.to_thread(_send_email_sync, subject, body)


async def send_pastoral_outreach_notification(telegram_user_id: int, language: str = "en") -> bool:
    """
    K-06: staff-facing alert sent only when a parishioner explicitly agrees ("Yes") to be
    contacted after the frequency-escalation offer — distinct from the crisis alert, which
    fires unconditionally on a crisis flag. Same SMTP settings/recipients, different content.
    """
    subject = get_string("comfort_escalation_email_subject", language)
    body = get_string("comfort_escalation_email_body", language).format(telegram_user_id=telegram_user_id)
    return await asyncio.to_thread(_send_email_sync, subject, body)


def _send_email_sync(subject: str, body: str) -> bool:
    try:
        recipients = json.loads(settings.contact_email_recipients)
    except (json.JSONDecodeError, TypeError):
        recipients = []
    if not recipients or not settings.smtp_host:
        logger.error("Notification email not configured — recipients or SMTP host missing")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_address or settings.smtp_username
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logger.error("Failed to send notification email: %s", exc)
        return False
