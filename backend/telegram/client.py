import logging

import httpx2

from config import settings
from telegram.formatting import split_message

logger = logging.getLogger(__name__)


def _log_request_error(action: str, exc: httpx2.RequestError) -> None:
    """httpx2.TransportError (connect/read timeouts, DNS failures, refused
    connections, etc.) means the network path to Telegram is broken — VPN,
    firewall, or ISP — not that the app is broken."""
    if isinstance(exc, httpx2.TransportError):
        logger.error(
            "Could not %s: %s. This looks like a network problem reaching Telegram "
            "(VPN, firewall, or ISP blocking api.telegram.org), not an application bug.",
            action,
            exc,
        )
    else:
        logger.error("Could not %s: %s", action, exc)


async def check_connectivity() -> bool:
    """Lightweight reachability probe for api.telegram.org, used by the /health
    endpoint so network outages are visible on demand and easier to diagnose."""
    async with httpx2.AsyncClient() as http:
        try:
            await http.get("https://api.telegram.org", timeout=3.0)
            return True
        except httpx2.RequestError as exc:
            _log_request_error("reach Telegram for a connectivity check", exc)
            return False


async def register_webhook() -> None:
    """
    Whether Telegram's API can't be reached at all, or is reached but rejects the
    request (bad token, malformed URL, etc.), there's nothing useful this instance can
    do either way — both are logged and re-raised deliberately, rather than booting 
    into a state that looks healthy but can never receive an update. Docker's restart 
    policy (docker-compose.yml) retries automatically, which covers transient outages 
    without any custom retry logic here. A persistent misconfiguration will keep 
    crash-looping until it's fixed, which is the correct, visible signal for that case.
    """
    async with httpx2.AsyncClient() as http:
        try:
            resp = await http.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                json={
                    "url": settings.telegram_webhook_url,
                    "secret_token": settings.telegram_webhook_secret,
                },
                timeout=10.0,
            )
        except httpx2.RequestError as exc:
            _log_request_error("reach Telegram to register webhook", exc)
            raise
        if not resp.is_success:
            logger.error("setWebhook failed: status=%d body=%s", resp.status_code, resp.text)
            raise RuntimeError(f"setWebhook failed: status={resp.status_code} body={resp.text}")
        logger.info("Webhook registered: %s", settings.telegram_webhook_url)


async def delete_webhook() -> None:
    """Runs during shutdown, so a failure here is logged and swallowed rather than
    raised since the process is exiting any way."""
    async with httpx2.AsyncClient() as http:
        try:
            await http.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/deleteWebhook",
                timeout=10.0,
            )
        except httpx2.RequestError as exc:
            _log_request_error("reach Telegram to delete webhook", exc)
            return
    logger.info("Webhook deleted")


async def send_message(chat_id: int, text: str, buttons: list[tuple[str, str]] | None = None) -> bool:
    """buttons is a list of (label, callback_data) pairs, rendered as one row of inline
    buttons attached to the final message part (if the text is long enough to be split)."""
    parts = split_message(text)
    success = True
    async with httpx2.AsyncClient() as http:
        for i, part in enumerate(parts):
            payload = {"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}
            if buttons and i == len(parts) - 1:
                payload["reply_markup"] = {
                    "inline_keyboard": [[{"text": label, "callback_data": data} for label, data in buttons]]
                }
            try:
                resp = await http.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json=payload,
                    timeout=10.0,
                )
            except httpx2.RequestError as exc:
                _log_request_error(f"send message to chat {chat_id}", exc)
                return False
            if not resp.is_success:
                logger.error("sendMessage failed: status=%d body=%s", resp.status_code, resp.text)
                success = False
    return success


async def answer_callback_query(callback_query_id: str) -> None:
    """Clears the loading spinner on a tapped inline button. Telegram doesn't do this
    automatically — without it, the button stays in a "loading" state client-side."""
    async with httpx2.AsyncClient() as http:
        try:
            resp = await http.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=10.0,
            )
        except httpx2.RequestError as exc:
            _log_request_error(f"answer callback query {callback_query_id}", exc)
            return
        if not resp.is_success:
            logger.error("answerCallbackQuery failed: status=%d body=%s", resp.status_code, resp.text)
