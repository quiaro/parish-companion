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
            "/start — Welcome message"
        ),
        "telegram_cmd_unknown": (
            "Sorry, I don't recognize that command. Type /help to see what I can do."
        ),
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
            "/start — Mensaje de bienvenida"
        ),
        "telegram_cmd_unknown": (
            "Lo siento, no reconozco ese comando. Escribe /help para ver lo que puedo hacer."
        ),
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
