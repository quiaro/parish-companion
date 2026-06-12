import json
import logging
from typing import cast

from redis.asyncio import Redis

from config import settings

logger = logging.getLogger(__name__)

_MAX_TURNS = 10


def _key(session_id: str) -> str:
    return f"session:{session_id}:history"


def _lang_key(session_id: str) -> str:
    return f"session:{session_id}:language"


async def get_history(session_id: str) -> list[dict]:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            raw_items = await r.lrange(_key(session_id), 0, -1)
        return [json.loads(item) for item in raw_items]
    except Exception as exc:
        logger.error("get_history failed session=%s: %s", session_id, exc)
        return []


async def get_language(session_id: str) -> str | None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            return cast(str | None, await r.get(_lang_key(session_id)))
    except Exception as exc:
        logger.error("get_language failed session=%s: %s", session_id, exc)
        return None


async def set_language(session_id: str, language: str) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.set(_lang_key(session_id), language, ex=settings.session_ttl_seconds)
    except Exception as exc:
        logger.error("set_language failed session=%s: %s", session_id, exc)


async def append_turn(session_id: str, user_text: str, bot_answer: str) -> None:
    key = _key(session_id)
    turns = [
        json.dumps({"role": "user", "content": user_text}),
        json.dumps({"role": "assistant", "content": bot_answer}),
    ]
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            pipe = r.pipeline()
            for turn in turns:
                pipe.rpush(key, turn)
            # Keep only the last MAX_TURNS * 2 messages (each turn = 2 messages)
            pipe.ltrim(key, -(_MAX_TURNS * 2), -1)
            pipe.expire(key, settings.session_ttl_seconds)
            await pipe.execute()
    except Exception as exc:
        logger.error("append_turn failed session=%s: %s", session_id, exc)
