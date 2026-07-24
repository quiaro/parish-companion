import logging

import httpx2

from config import settings
from telegram.formatting import split_message

logger = logging.getLogger(__name__)


async def register_webhook() -> None:
    if not settings.telegram_webhook_url:
        logger.info("TELEGRAM_WEBHOOK_URL not set, skipping webhook registration")
        return
    async with httpx2.AsyncClient() as http:
        resp = await http.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
            json={
                "url": settings.telegram_webhook_url,
                "secret_token": settings.telegram_webhook_secret,
            },
            timeout=10.0,
        )
        if resp.is_success:
            logger.info("Webhook registered: %s", settings.telegram_webhook_url)
        else:
            logger.error("setWebhook failed: status=%d body=%s", resp.status_code, resp.text)


async def delete_webhook() -> None:
    if not settings.telegram_webhook_url:
        return
    async with httpx2.AsyncClient() as http:
        await http.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/deleteWebhook",
            timeout=10.0,
        )
    logger.info("Webhook deleted")


async def send_message(chat_id: int, text: str, buttons: list[tuple[str, str]] | None = None) -> bool:
    """buttons is a list of (label, callback_data) pairs, rendered as one row of inline
    buttons attached to the final message part (if the text is long enough to be split)."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping outbound message to chat_id=%d", chat_id)
        return False
    parts = split_message(text)
    success = True
    async with httpx2.AsyncClient() as http:
        for i, part in enumerate(parts):
            payload = {"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}
            if buttons and i == len(parts) - 1:
                payload["reply_markup"] = {
                    "inline_keyboard": [[{"text": label, "callback_data": data} for label, data in buttons]]
                }
            resp = await http.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json=payload,
                timeout=10.0,
            )
            if not resp.is_success:
                logger.error("sendMessage failed: status=%d body=%s", resp.status_code, resp.text)
                success = False
    return success


async def answer_callback_query(callback_query_id: str) -> None:
    """Clears the loading spinner on a tapped inline button. Telegram doesn't do this
    automatically — without it, the button stays in a "loading" state client-side."""
    if not settings.telegram_bot_token:
        return
    async with httpx2.AsyncClient() as http:
        resp = await http.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id},
            timeout=10.0,
        )
        if not resp.is_success:
            logger.error("answerCallbackQuery failed: status=%d body=%s", resp.status_code, resp.text)
