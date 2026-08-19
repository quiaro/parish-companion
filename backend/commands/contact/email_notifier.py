import json
import logging
import smtplib
from email.message import EmailMessage

from commands.contact.models import ContactRequest
from commands.contact.notifier import ContactNotifier
from config import settings
from translations import get_string

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    try:
        recipients = json.loads(settings.contact_email_recipients)
    except (json.JSONDecodeError, TypeError):
        recipients = []
    return bool(recipients) and bool(settings.smtp_host)


class EmailContactNotifier(ContactNotifier):

    def send(self, request: ContactRequest) -> bool:
        if not is_configured():
            logger.error("Contact email not configured — recipients or SMTP host missing")
            return False
        try:
            recipients = json.loads(settings.contact_email_recipients)
            msg = EmailMessage()
            msg["Subject"] = f"Parish Companion: {request.request_type}"
            msg["From"] = settings.smtp_from_address or settings.smtp_username
            msg["To"] = ", ".join(recipients)
            msg.set_content(self._format_body(request))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
            return True
        except Exception as exc:
            logger.error("Failed to send contact email: %s", exc)
            return False

    def _format_body(self, request: ContactRequest) -> str:
        lang = request.language
        if request.telegram_username:
            telegram = f"@{request.telegram_username} (ID: {request.telegram_user_id})"
        else:
            telegram = f"ID: {request.telegram_user_id}"
        return (
            f"{get_string('contact_email_intro', lang)}\n\n"
            f"{get_string('contact_email_label_request_type', lang)} {request.request_type}\n"
            f"{get_string('contact_email_label_name', lang)} {request.name}\n"
            f"{get_string('contact_email_label_telegram', lang)} {telegram}\n"
            f"{get_string('contact_email_label_message', lang)}\n{request.message}\n\n"
            f"{get_string('contact_email_label_preferred_time', lang)} {request.preferred_time}\n"
        )
