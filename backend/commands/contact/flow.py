import asyncio
import json
import logging

from redis.asyncio import Redis

from commands.contact.models import ContactRequest
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


def _format_request_type_question(language: str) -> str:
    types = _get_request_types(language)
    options = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(types))
    return f"{get_string('contact_ask_request_type', language)}\n\n{options}"


def _question_for_step(step: str, language: str) -> str:
    if step == "request_type":
        return _format_request_type_question(language)
    return get_string(_STEP_QUESTION_KEYS[step], language)


async def start(session_id: str, language: str) -> str:
    state: dict = {"step": "name", "language": language, "answers": {}}
    await _set_state(session_id, state)
    return _question_for_step("name", language)


async def advance(session_id: str, text: str) -> tuple[str, bool]:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("advance called with no active flow session=%s", session_id)
        return get_string("telegram_cmd_unknown", "en"), False

    step = state["step"]
    language = state["language"]

    if step == "done":
        return get_string("contact_intake_complete", language), True

    if step == "request_type":
        types = _get_request_types(language)
        try:
            idx = int(text.strip()) - 1
            if not (0 <= idx < len(types)):
                raise ValueError
        except ValueError:
            re_ask = _format_request_type_question(language)
            return f"{re_ask}\n\n{get_string('contact_invalid_choice', language)}", False
        state["answers"]["request_type"] = types[idx]
    else:
        state["answers"][step] = text.strip()

    current_index = STEPS.index(step)
    if current_index + 1 < len(STEPS):
        next_step = STEPS[current_index + 1]
        state["step"] = next_step
        await _set_state(session_id, state)
        return _question_for_step(next_step, language), False

    state["step"] = "done"
    await _set_state(session_id, state)
    return get_string("contact_intake_complete", language), True


_YES_TOKENS = {"yes", "y", "sí", "si", "s"}
_NO_TOKENS = {"no", "n"}


def _format_summary(answers: dict, language: str) -> str:
    lines = [
        get_string("contact_confirm_summary_header", language),
        "",
        f"{get_string('contact_email_label_request_type', language)} {answers.get('request_type', '')}",
        f"{get_string('contact_email_label_name', language)} {answers.get('name', '')}",
        f"{get_string('contact_email_label_message', language)} {answers.get('message', '')}",
        f"{get_string('contact_email_label_preferred_time', language)} {answers.get('preferred_time', '')}",
    ]
    return "\n".join(lines)


async def present_confirmation(session_id: str) -> str:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("present_confirmation called with no active flow session=%s", session_id)
        return get_string("telegram_cmd_unknown", "en")
    language = state["language"]
    summary = _format_summary(state["answers"], language)
    state["step"] = "confirm"
    await _set_state(session_id, state)
    return f"{summary}\n\n{get_string('contact_confirm_prompt', language)}"


async def submit(
    session_id: str,
    text: str,
    notifier: ContactNotifier,
    telegram_user_id: int,
    telegram_username: str | None,
) -> str:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("submit called with no active flow session=%s", session_id)
        return get_string("telegram_cmd_unknown", "en")
    language = state["language"]
    normalized = text.strip().lower()

    if normalized in _NO_TOKENS:
        await _clear_state(session_id)
        return get_string("contact_cancelled", language)

    if normalized not in _YES_TOKENS:
        summary = _format_summary(state["answers"], language)
        return f"{summary}\n\n{get_string('contact_confirm_re_ask', language)}"

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
        return get_string("contact_confirm_success", language)

    # State kept at "confirm" so the user can retry
    if settings.contact_phone:
        return get_string("contact_confirm_send_error_with_phone", language).format(
            phone=settings.contact_phone
        )
    return get_string("contact_confirm_send_error", language)


async def cancel(session_id: str) -> str:
    state = await _get_state(session_id)
    language = state["language"] if state else "en"
    await _clear_state(session_id)
    return get_string("contact_cancelled", language)


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
