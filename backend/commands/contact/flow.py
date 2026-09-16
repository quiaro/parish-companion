import asyncio
import json
import logging

from redis.asyncio import Redis

from commands.contact.models import ContactFlowReply, ContactRequest
from commands.contact.notifier import ContactNotifier
from config import settings
from translations import get_string

logger = logging.getLogger(__name__)

_CONTACT_KEY = "session:{}:contact"

STEPS = ["name", "request_type", "message", "preferred_time"]

_STEP_QUESTION_KEYS: dict[str, str] = {
    "name": "contact_ask_name",
    "message": "contact_ask_message",
    "preferred_time": "contact_ask_preferred_time",
}


async def _get_state(session_id: str) -> dict | None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            raw = await r.get(_CONTACT_KEY.format(session_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.error("contact flow _get_state failed session=%s: %s", session_id, exc)
        return None


async def _set_state(session_id: str, state: dict) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.set(
                _CONTACT_KEY.format(session_id),
                json.dumps(state),
                ex=settings.session_ttl_seconds,
            )
    except Exception as exc:
        logger.error("contact flow _set_state failed session=%s: %s", session_id, exc)


async def _clear_state(session_id: str) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.delete(_CONTACT_KEY.format(session_id))
    except Exception as exc:
        logger.error("contact flow _clear_state failed session=%s: %s", session_id, exc)


def _get_request_types(language: str) -> list[str]:
    try:
        if language == "es" and settings.contact_request_types_es:
            return json.loads(settings.contact_request_types_es)
        return json.loads(settings.contact_request_types)
    except (json.JSONDecodeError, TypeError):
        return []


_CALLBACK_REQUEST_TYPE_PREFIX = "contact_reqtype"


def _request_type_callback(index: int) -> str:
    return f"{_CALLBACK_REQUEST_TYPE_PREFIX}|{index}"


def _parse_request_type_index(callback_data: str) -> int | None:
    prefix, sep, rest = callback_data.partition("|")
    if not sep or prefix != _CALLBACK_REQUEST_TYPE_PREFIX:
        return None
    try:
        return int(rest)
    except ValueError:
        return None


def _build_request_type_reply(language: str) -> ContactFlowReply:
    types = _get_request_types(language)
    return ContactFlowReply(
        text=get_string("contact_ask_request_type", language),
        button_rows=[[(label, _request_type_callback(i))] for i, label in enumerate(types)],
    )


def _reply_for_step(step: str, language: str) -> ContactFlowReply:
    if step == "request_type":
        return _build_request_type_reply(language)
    return ContactFlowReply(text=get_string(_STEP_QUESTION_KEYS[step], language))


async def start(session_id: str, language: str) -> str:
    state: dict = {"step": "name", "language": language, "answers": {}}
    await _set_state(session_id, state)
    return _reply_for_step("name", language).text


async def advance(session_id: str, text: str) -> tuple[ContactFlowReply, bool]:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("advance called with no active flow session=%s", session_id)
        return ContactFlowReply(text=get_string("telegram_cmd_unknown", "en")), False

    step = state["step"]
    language = state["language"]

    if step == "done":
        return ContactFlowReply(text=get_string("contact_intake_complete", language)), True

    state["answers"][step] = text.strip()

    current_index = STEPS.index(step)
    if current_index + 1 < len(STEPS):
        next_step = STEPS[current_index + 1]
        state["step"] = next_step
        await _set_state(session_id, state)
        return _reply_for_step(next_step, language), False

    state["step"] = "done"
    await _set_state(session_id, state)
    return ContactFlowReply(text=get_string("contact_intake_complete", language)), True


_CALLBACK_SEND = "contact_confirm_send"
_CALLBACK_CANCEL = "contact_confirm_cancel"


def _format_summary(answers: dict, language: str) -> str:
    lines = [
        get_string("contact_confirm_summary_header", language),
        "",
        f"{get_string('contact_email_label_name', language)} {answers.get('name', '')}",
        f"{get_string('contact_email_label_request_type', language)} {answers.get('request_type', '')}",
        f"_{answers.get('message', '')}_",
        f"{get_string('contact_email_label_preferred_time', language)} {answers.get('preferred_time', '')}",
    ]
    return "\n".join(lines)


async def present_confirmation(session_id: str) -> ContactFlowReply:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("present_confirmation called with no active flow session=%s", session_id)
        return ContactFlowReply(text=get_string("telegram_cmd_unknown", "en"))
    language = state["language"]
    summary = _format_summary(state["answers"], language)
    state["step"] = "confirm"
    await _set_state(session_id, state)
    return ContactFlowReply(
        text=summary,
        buttons=[
            (get_string("contact_button_send", language), _CALLBACK_SEND),
            (get_string("contact_button_cancel", language), _CALLBACK_CANCEL),
        ],
    )


async def handle_callback(
    session_id: str,
    callback_data: str,
    notifier: ContactNotifier,
    telegram_user_id: int,
    telegram_username: str | None,
) -> ContactFlowReply | None:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("handle_callback called with no active flow session=%s data=%s", session_id, callback_data)
        return None

    step = state.get("step")
    if step == "request_type":
        return await _handle_request_type_callback(session_id, state, callback_data)
    if step == "confirm":
        return await _handle_confirm_callback(
            session_id, state, callback_data, notifier, telegram_user_id, telegram_username
        )

    logger.warning(
        "handle_callback called with mismatched step=%s data=%s session=%s", step, callback_data, session_id
    )
    return None


async def _handle_request_type_callback(
    session_id: str, state: dict, callback_data: str
) -> ContactFlowReply:
    language = state["language"]
    types = _get_request_types(language)
    idx = _parse_request_type_index(callback_data)

    if idx is None or not (0 <= idx < len(types)):
        logger.warning(
            "stale/invalid request_type callback idx=%s data=%s session=%s", idx, callback_data, session_id
        )
        reply = _build_request_type_reply(language)
        reply.text = f"{reply.text}\n\n{get_string('contact_invalid_choice', language)}"
        return reply

    state["answers"]["request_type"] = types[idx]
    next_step = STEPS[STEPS.index("request_type") + 1]
    state["step"] = next_step
    await _set_state(session_id, state)
    return _reply_for_step(next_step, language)


async def _handle_confirm_callback(
    session_id: str,
    state: dict,
    callback_data: str,
    notifier: ContactNotifier,
    telegram_user_id: int,
    telegram_username: str | None,
) -> ContactFlowReply | None:
    if callback_data not in (_CALLBACK_SEND, _CALLBACK_CANCEL):
        logger.warning(
            "handle_callback called with mismatched step=confirm data=%s session=%s", callback_data, session_id
        )
        return None

    language = state["language"]

    if callback_data == _CALLBACK_CANCEL:
        await _clear_state(session_id)
        return ContactFlowReply(text=get_string("contact_cancelled", language), flow_ended=True)

    answers = state["answers"]
    contact_request = ContactRequest(
        name=answers["name"],
        request_type=answers["request_type"],
        message=answers["message"],
        preferred_time=answers["preferred_time"],
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
        language=language,
    )
    if await asyncio.to_thread(notifier.send, contact_request):
        await _clear_state(session_id)
        return ContactFlowReply(text=get_string("contact_confirm_success", language), flow_ended=True)

    # State kept at "confirm" so the user can retry by tapping Send again
    if settings.contact_phone:
        return ContactFlowReply(
            text=get_string("contact_confirm_send_error_with_phone", language).format(
                phone=settings.contact_phone
            )
        )
    return ContactFlowReply(text=get_string("contact_confirm_send_error", language))


async def cancel(session_id: str) -> str:
    state = await _get_state(session_id)
    language = state["language"] if state else "en"
    await _clear_state(session_id)
    return get_string("contact_cancelled", language)


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
