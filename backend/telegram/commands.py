from commands.comfort import is_configured as comfort_is_configured
from commands.contact import is_configured as contact_is_configured
from translations import get_string

# (translation_key, forced_language | None)
# None means use the caller's detected language.
_KEY_MAP: dict[str, tuple[str, str | None]] = {
    "/start":  ("telegram_cmd_start", "en"),
    "/inicio": ("telegram_cmd_start", "es"),
}

_HELP_COMMAND_LANGUAGES: dict[str, str] = {
    "/help": "en",
    "/ayuda": "es",
}


def _build_help_reply(language: str) -> str:
    lines = [get_string("help_intro", language)]
    if comfort_is_configured():
        lines.append(get_string("help_line_comfort", language))
    if contact_is_configured():
        lines.append(get_string("help_line_contact", language))
    lines.append(get_string("help_line_schedules", language))
    return "".join(lines)


def get_reply(command: str, language: str = "en") -> str:
    if command in _HELP_COMMAND_LANGUAGES:
        return _build_help_reply(_HELP_COMMAND_LANGUAGES[command])
    key, forced_language = _KEY_MAP.get(command, ("telegram_cmd_unknown", None))
    return get_string(key, forced_language or language)
