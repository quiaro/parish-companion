import asyncio
import json
import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger(__name__)


async def send_crisis_notification(telegram_user_id: int) -> bool:
    """
    Urgent, staff-facing alert for a /comfort message flagged as a possible crisis
    (self-harm, suicidal ideation, sexual abuse, or physical violence). Reuses the same
    SMTP settings and recipient list as /contact, but isn't a ContactRequest — this is a
    system-triggered alert, not a parishioner-submitted intake form.
    """
    return await asyncio.to_thread(_send_crisis_notification_sync, telegram_user_id)


def _send_crisis_notification_sync(telegram_user_id: int) -> bool:
    try:
        recipients = json.loads(settings.contact_email_recipients)
    except (json.JSONDecodeError, TypeError):
        recipients = []
    if not recipients or not settings.smtp_host:
        logger.error("Crisis notification email not configured — recipients or SMTP host missing")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = "Parish Companion: Urgent — /comfort crisis flag"
        msg["From"] = settings.smtp_from_address or settings.smtp_username
        msg["To"] = ", ".join(recipients)
        msg.set_content(
            "A parishioner's message through /comfort was flagged as describing a possible "
            "crisis (self-harm, suicidal ideation, sexual abuse, or physical violence).\n\n"
            f"Telegram user ID: {telegram_user_id}\n\n"
            "Please follow up with this parishioner as soon as possible."
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logger.error("Failed to send crisis notification email: %s", exc)
        return False
