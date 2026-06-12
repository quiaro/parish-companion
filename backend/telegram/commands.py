from translations import get_string

_KEY_MAP: dict[str, str] = {
    "/start": "telegram_cmd_start",
    "/help": "telegram_cmd_help",
}


def get_reply(command: str, language: str = "en") -> str:
    key = _KEY_MAP.get(command, "telegram_cmd_unknown")
    return get_string(key, language)
