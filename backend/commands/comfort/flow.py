import asyncio
import json
import logging

from redis.asyncio import Redis

from commands.comfort.classifier import classify
from config import settings
from db.parishioners import ensure_parishioner, is_comfort_intro_shown, mark_comfort_intro_shown
from translations import get_string

logger = logging.getLogger(__name__)

_COMFORT_KEY = "session:{}:comfort"
_MAX_INPUT_LENGTH = 2000


async def _get_state(session_id: str) -> dict | None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            raw = await r.get(_COMFORT_KEY.format(session_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.error("comfort flow _get_state failed session=%s: %s", session_id, exc)
        return None


async def _set_state(session_id: str, state: dict) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.set(
                _COMFORT_KEY.format(session_id),
                json.dumps(state),
                ex=settings.session_ttl_seconds,
            )
    except Exception as exc:
        logger.error("comfort flow _set_state failed session=%s: %s", session_id, exc)


async def _clear_state(session_id: str) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.delete(_COMFORT_KEY.format(session_id))
    except Exception as exc:
        logger.error("comfort flow _clear_state failed session=%s: %s", session_id, exc)


async def start(session_id: str, telegram_user_id: int, language: str = "en") -> str:
    await asyncio.to_thread(ensure_parishioner, telegram_user_id)

    if await asyncio.to_thread(is_comfort_intro_shown, telegram_user_id):
        reply = get_string("comfort_brief_intro", language)
    else:
        await asyncio.to_thread(mark_comfort_intro_shown, telegram_user_id)
        reply = get_string("comfort_intro", language)

    await _set_state(session_id, {"language": language, "telegram_user_id": telegram_user_id})
    return reply


async def handle_text(session_id: str, text: str) -> str:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("handle_text called with no active flow session=%s", session_id)
        return get_string("telegram_cmd_unknown", "en")

    language = state["language"]
    stripped = text.strip()

    if len(stripped) > _MAX_INPUT_LENGTH:
        return get_string("comfort_input_too_long", language)

    try:
        await classify(stripped)
    except Exception as exc:
        # Retrieval/crisis-gating (Steps C-K) aren't wired in yet, so nothing currently
        # acts on the classification result — don't let a classifier failure block the
        # parishioner from getting a reply.
        logger.error("classify failed session=%s: %s", session_id, exc)

    await _clear_state(session_id)
    return get_string("comfort_ack_placeholder", language)


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
