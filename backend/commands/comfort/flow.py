import asyncio

from db.parishioners import ensure_parishioner, is_comfort_intro_shown, mark_comfort_intro_shown
from translations import get_string


async def start(telegram_user_id: int, language: str = "en") -> str:
    await asyncio.to_thread(ensure_parishioner, telegram_user_id)

    if await asyncio.to_thread(is_comfort_intro_shown, telegram_user_id):
        return get_string("comfort_prompt_brief", language)

    await asyncio.to_thread(mark_comfort_intro_shown, telegram_user_id)
    return get_string("comfort_intro", language)
