from commands.comfort.flow import start
from config import settings

__all__ = ["is_configured", "start"]


def is_configured() -> bool:
    return bool(
        settings.openrouter_api_key
        and settings.openrouter_chat_model
        and settings.openrouter_embedding_model
    )
