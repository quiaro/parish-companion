import logging

import httpx

from config import settings
from telegram.formatting import split_message

logger = logging.getLogger(__name__)


async def register_webhook() -> None:
    if not settings.telegram_webhook_url:
        logger.info("TELEGRAM_WEBHOOK_URL not set, skipping webhook registration")
        return
    async with httpx.AsyncClient() as http:
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
    async with httpx.AsyncClient() as http:
        await http.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/deleteWebhook",
            timeout=10.0,
        )
    logger.info("Webhook deleted")


async def send_message(chat_id: int, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping outbound message to chat_id=%d", chat_id)
        return
    async with httpx.AsyncClient() as http:
        for part in split_message(text):
            resp = await http.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": part, "parse_mode": "Markdown"},
                timeout=10.0,
            )
            if not resp.is_success:
                logger.error("sendMessage failed: status=%d body=%s", resp.status_code, resp.text)
