import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from commands.comfort import flow as comfort_flow
from commands.comfort import is_configured as comfort_is_configured
from commands.contact import flow as contact_flow
from commands.contact import is_configured as contact_is_configured
from commands.information import is_configured as information_is_configured
from commands.schedules import is_configured as schedules_is_configured
from config import settings
from session import get_language
from telegram import commands
from telegram import information as telegram_information
from telegram import schedule as telegram_schedule
from telegram.client import answer_callback_query, send_message
from telegram.models import CallbackQuery, Update
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

_COMFORT_COMMAND_LANGUAGES: dict[str, str] = {
    "/comfort": "en",
    "/consolar": "es",
}

_INFORMATION_COMMAND_LANGUAGES: dict[str, str] = {
    "/information": "en",
    "/información": "es",
}


async def _handle_callback_query(request: Request, callback_query: CallbackQuery) -> JSONResponse:
    await answer_callback_query(callback_query.id)

    if callback_query.message is None or callback_query.data is None:
        return JSONResponse({"status": "ok"})

    chat_id = callback_query.message.chat.id
    session_id = str(chat_id)

    if information_is_configured():
        parsed = telegram_information.parse_callback(callback_query.data)
        if parsed is not None:
            action, key = parsed
            if action == telegram_information.TOPIC_ACTION and key is not None:
                info_reply = telegram_information.handle_topic_selection(
                    request.app.state.information_adapter, key
                )
                if info_reply is not None:
                    await send_message(chat_id, info_reply.text, button_rows=info_reply.button_rows)
            # MENU_ACTION ("Back to menu") is not yet wired up — I-06.
            return JSONResponse({"status": "ok"})

    comfort_state = await comfort_flow.get_state(session_id)
    if comfort_state:
        reply = await comfort_flow.handle_callback(session_id, callback_query.data)
        if reply is not None:
            sent = await send_message(chat_id, reply.text, buttons=reply.buttons)
            if sent and reply.record_passage_on_success:
                await comfort_flow.confirm_passage_sent(session_id)

    return JSONResponse({"status": "ok"})


@router.post("/webhook")
async def receive_update(
    request: Request,
    update: Update,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    _verify_secret(x_telegram_bot_api_secret_token)

    if update.callback_query is not None:
        return await _handle_callback_query(request, update.callback_query)

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
        if command in _SCHEDULE_COMMAND_LANGUAGES and schedules_is_configured():
            forced_lang = _SCHEDULE_COMMAND_LANGUAGES[command]
            reply = telegram_schedule.handle_schedules(request.app.state.schedule_adapter, forced_lang)
        elif command in _CONTACT_COMMAND_LANGUAGES and contact_is_configured():
            forced_lang = _CONTACT_COMMAND_LANGUAGES[command]
            reply = await contact_flow.start(session_id, forced_lang)
        elif command in _COMFORT_COMMAND_LANGUAGES and comfort_is_configured():
            forced_lang = _COMFORT_COMMAND_LANGUAGES[command]
            reply = await comfort_flow.start(session_id, sender.id if sender else chat_id, forced_lang)
        elif command in _INFORMATION_COMMAND_LANGUAGES and information_is_configured():
            forced_lang = _INFORMATION_COMMAND_LANGUAGES[command]
            info_reply = telegram_information.handle_command(request.app.state.information_adapter, forced_lang)
            await send_message(chat_id, info_reply.text, button_rows=info_reply.button_rows)
            return JSONResponse({"status": "ok"})
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
        if reply is not None:
            sent = await send_message(chat_id, reply.text, buttons=reply.buttons)
            if sent and reply.record_passage_on_success:
                await comfort_flow.confirm_passage_sent(session_id)
        return JSONResponse({"status": "ok"})

    # Plain text outside of any active flow (likely a new or confused parishioner).
    await send_message(chat_id, get_string("telegram_cmd_start", language))
    return JSONResponse({"status": "ok"})
