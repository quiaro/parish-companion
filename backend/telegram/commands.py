from commands.comfort import is_configured as comfort_is_configured
from commands.contact import is_configured as contact_is_configured
from commands.information import is_configured as information_is_configured
from commands.schedules import is_configured as schedules_is_configured
from config import settings
from translations import get_start_message, get_string

_START_COMMAND_LANGUAGES: dict[str, str] = {
    "/start": "en",
    "/inicio": "es",
}

_HELP_COMMAND_LANGUAGES: dict[str, str] = {
    "/help": "en",
    "/ayuda": "es",
}


def build_help_reply(language: str) -> str:
    lines = [get_string("help_intro", language)]
    if comfort_is_configured():
        lines.append(get_string("help_line_comfort", language))
    if contact_is_configured():
        lines.append(get_string("help_line_contact", language))
    if schedules_is_configured():
        lines.append(get_string("help_line_schedules", language))
    if information_is_configured():
        lines.append(get_string("help_line_information", language))
    return "".join(lines)


def get_reply(command: str, language: str = "en") -> str:
    if command in _HELP_COMMAND_LANGUAGES:
        return build_help_reply(_HELP_COMMAND_LANGUAGES[command])
    if command in _START_COMMAND_LANGUAGES:
        supported = settings.supported_languages_list
        start_language = supported[0] if len(supported) == 1 else _START_COMMAND_LANGUAGES[command]
        return get_start_message(start_language)
    return get_string("telegram_cmd_unknown", language)
