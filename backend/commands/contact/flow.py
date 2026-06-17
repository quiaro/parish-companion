import json
import logging

from redis.asyncio import Redis

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


async def cancel(session_id: str) -> str:
    state = await _get_state(session_id)
    language = state["language"] if state else "en"
    await _clear_state(session_id)
    return get_string("contact_cancelled", language)


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
