import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from commands.comfort import flow as comfort_flow
from commands.contact import flow as contact_flow
from config import settings
from session import get_language
from telegram import commands
from telegram import schedule as telegram_schedule
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


_SCHEDULE_COMMAND_LANGUAGES: dict[str, str] = {
    "/schedules": "en",
    "/horarios": "es",
}

_CONTACT_COMMAND_LANGUAGES: dict[str, str] = {
    "/contact": "en",
    "/contacto": "es",
}

# /consolar and Spanish copy are covered by a separate localization story — English only for now.
_COMFORT_COMMAND_LANGUAGES: dict[str, str] = {
    "/comfort": "en",
}


@router.post("/webhook")
async def receive_update(
    request: Request,
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

    sender = update.message.from_

    text = update.message.text
    if text.startswith("/"):
        command = text.split()[0].split("@")[0].lower()
        if command in _SCHEDULE_COMMAND_LANGUAGES:
            forced_lang = _SCHEDULE_COMMAND_LANGUAGES[command]
            reply = telegram_schedule.handle_schedules(request.app.state.schedule_adapter, forced_lang)
        elif command in _CONTACT_COMMAND_LANGUAGES:
            forced_lang = _CONTACT_COMMAND_LANGUAGES[command]
            reply = await contact_flow.start(session_id, forced_lang)
        elif command in _COMFORT_COMMAND_LANGUAGES:
            forced_lang = _COMFORT_COMMAND_LANGUAGES[command]
            reply = await comfort_flow.start(session_id, sender.id if sender else chat_id, forced_lang)
        elif command == "/cancel":
            flow_state = await contact_flow.get_state(session_id)
            if flow_state:
                reply = await contact_flow.cancel(session_id)
            else:
                reply = commands.get_reply(command, language)
        else:
            reply = commands.get_reply(command, language)
        await send_message(chat_id, reply)
        return JSONResponse({"status": "ok"})

    flow_state = await contact_flow.get_state(session_id)
    if flow_state:
        step = flow_state["step"]
        if step == "confirm":
            reply = await contact_flow.submit(
                session_id,
                text,
                request.app.state.contact_notifier,
                sender.id if sender else chat_id,
                sender.username if sender else None,
            )
        elif step == "done":
            reply = await contact_flow.present_confirmation(session_id)
        else:
            reply, done = await contact_flow.advance(session_id, text)
            if done:
                reply = await contact_flow.present_confirmation(session_id)
        await send_message(chat_id, reply)
        return JSONResponse({"status": "ok"})

    comfort_state = await comfort_flow.get_state(session_id)
    if comfort_state:
        reply = await comfort_flow.handle_text(session_id, text)
        await send_message(chat_id, reply)
        return JSONResponse({"status": "ok"})

    return JSONResponse({"status": "ok"})
