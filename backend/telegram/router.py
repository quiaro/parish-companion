import logging

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from config import settings
from session import get_language
from telegram import commands
from telegram.client import send_message
from telegram.models import Update
from translations import get_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _verify_secret(secret_token: str | None) -> None:
    expected = settings.telegram_webhook_secret
    if not expected:
        return
    if secret_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret token",
        )


@router.post("/webhook")
async def receive_update(
    update: Update,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    _verify_secret(x_telegram_bot_api_secret_token)

    if update.message is None:
        return JSONResponse({"status": "ok"})

    chat_id = update.message.chat.id
    session_id = str(chat_id)
    logger.info("update=%d session=%s", update.update_id, session_id)

    language = await get_language(session_id) or settings.default_language

    if update.message.text is None:
        await send_message(chat_id, get_string("telegram_text_only", language))
        return JSONResponse({"status": "ok"})

    text = update.message.text
    if text.startswith("/"):
        command = text.split()[0].split("@")[0].lower()
        await send_message(chat_id, commands.get_reply(command, language))
        return JSONResponse({"status": "ok"})

    # TODO: Implement actual message handling.
    # reply = await handle_message(text, session_id, pool)
    return JSONResponse({"status": "ok"})
