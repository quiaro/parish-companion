from translations import get_string

# (translation_key, forced_language | None)
# None means use the caller's detected language.
_KEY_MAP: dict[str, tuple[str, str | None]] = {
    "/start":  ("telegram_cmd_start", "en"),
    "/inicio": ("telegram_cmd_start", "es"),
    "/help":   ("telegram_cmd_help",  "en"),
    "/ayuda":  ("telegram_cmd_help",  "es"),
}


def get_reply(command: str, language: str = "en") -> str:
    key, forced_language = _KEY_MAP.get(command, ("telegram_cmd_unknown", None))
    return get_string(key, forced_language or language)
