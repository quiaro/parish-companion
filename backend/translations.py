import logging

from config import settings

logger = logging.getLogger(__name__)

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "telegram_text_only": (
            "Sorry, I can only handle text messages. Please type your question."
        ),
        "telegram_cmd_start": (
            "Hello! This is the bot for Nuestra Señora del Pilar.\n"
        ),
        "telegram_cmd_help": (
            "Here is what I can do:\n\n"
            "/ayuda — Lista de comandos (español)\n"
            "/help — List available commands (English)\n"
            "/start — Welcome message\n"
            "/schedules — View Mass and Confession times"
        ),
        "telegram_cmd_unknown": (
            "Sorry, I don't recognize that command. Type /help to see what I can do."
        ),
        "schedule_mass_header": "Mass Times",
        "schedule_confession_header": "Confession",
        "schedule_no_confession": (
            "No Confession times are currently scheduled. "
            "For more information, use /contact or call the parish office."
        ),
        "schedule_unavailable": (
            "Sorry, I wasn't able to retrieve the schedule right now. "
            "Please check the parish website or use /contact for assistance."
        ),
        "schedule_upcoming_label": "Upcoming",
    },
    "es": {
        "telegram_text_only": (
            "Lo siento, sólo puedo responder mensajes de texto. Por favor, escribe tu pregunta."
        ),
        "telegram_cmd_start": (
            "¡Hola! Soy el bot de Nuestra Señora del Pilar.\n"
        ),
        "telegram_cmd_help": (
            "Esto es lo que puedo hacer:\n\n"
            "/ayuda — Lista de comandos (español)\n"
            "/help — List available commands (English)\n"
            "/inicio — Mensaje de bienvenida\n"
            "/horarios — Ver horarios de Misa y Confesiones"
        ),
        "telegram_cmd_unknown": (
            "Lo siento, no reconozco ese comando. Escribe /help para ver lo que puedo hacer."
        ),
        "schedule_mass_header": "Horarios de Misa",
        "schedule_confession_header": "Confesiones",
        "schedule_no_confession": (
            "Por el momento no hay horarios de confesión programados. "
            "Para más información, usa /contacto o llama a la parroquia."
        ),
        "schedule_unavailable": (
            "Lo siento, no pude obtener los horarios en este momento. "
            "Por favor visita el sitio web de la parroquia o usa /contacto para obtener ayuda."
        ),
        "schedule_upcoming_label": "Próximamente",
    },
}


def get_string(key: str, language: str) -> str:
    """Return the string for key in language, falling back to default_language. Logs an error and returns '' if the key is missing from all languages."""
    value = STRINGS.get(language, {}).get(key)
    if value is not None:
        return value
    value = STRINGS.get(settings.default_language, {}).get(key)
    if value is not None:
        return value
    logger.error("Missing translation key '%s' in all languages", key)
    return ""
