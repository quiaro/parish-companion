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
            "Use /help or /ayuda (Spanish) to know what I can do."
        ),
        "telegram_cmd_help": (
            "Here is what I can do:\n"
            "/help: List available commands\n"
            "/schedules: View Mass and Confession times\n"
            "/contact: Reach a member of our parish staff\n"
            "/start: Welcome message"
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
        "contact_email_intro": (
            "A parishioner has submitted a contact request through Parish Companion."
        ),
        "contact_email_label_request_type": "Request type:",
        "contact_email_label_name": "Name:",
        "contact_email_label_telegram": "Telegram contact:",
        "contact_email_label_message": "Message:",
        "contact_email_label_preferred_time": "Best time to reach:",
        "contact_ask_name": "What is your name?",
        "contact_ask_request_type": "What type of assistance are you looking for?",
        "contact_ask_message": "Please briefly describe what you need help with.",
        "contact_ask_preferred_time": (
            "What is the best time to reach you? (e.g. weekday mornings, evenings)"
        ),
        "contact_cancelled": (
            "Your request has been cancelled. Feel free to reach out again any time."
        ),
        "contact_invalid_choice": "Please enter a number from the list above.",
        "contact_intake_complete": "Thank you! We received your information and will be in touch soon.",
    },
    "es": {
        "telegram_text_only": (
            "Lo siento, sólo puedo responder mensajes de texto. Por favor, escribe tu pregunta."
        ),
        "telegram_cmd_start": (
            "¡Hola! Soy el bot de Nuestra Señora del Pilar.\n"
            "Utiliza /ayuda o /help (inglés) para ver lo que puedo hacer."
        ),
        "telegram_cmd_help": (
            "Esto es lo que puedo hacer:\n"
            "/ayuda: Lista de comandos\n"
            "/horarios: Ver horarios de Misa y Confesiones\n"
            "/contacto: Comunicarse con el personal de la parroquia\n"
            "/inicio: Mensaje de bienvenida"
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
        "contact_email_intro": (
            "Se ha enviado una solicitud de contacto a través de Parish Companion."
        ),
        "contact_email_label_request_type": "Tipo de solicitud:",
        "contact_email_label_name": "Nombre:",
        "contact_email_label_telegram": "Contacto de Telegram:",
        "contact_email_label_message": "Mensaje:",
        "contact_email_label_preferred_time": "Mejor horario para comunicarse:",
        "contact_ask_name": "¿Cuál es su nombre?",
        "contact_ask_request_type": "¿Qué tipo de ayuda está buscando?",
        "contact_ask_message": "Por favor, describa brevemente en qué necesita ayuda.",
        "contact_ask_preferred_time": (
            "¿Cuál es el mejor horario para comunicarnos con usted? "
            "(e.g. mañanas entre semana, por las tardes)"
        ),
        "contact_cancelled": (
            "Su solicitud ha sido cancelada. No dude en contactarnos cuando lo necesite."
        ),
        "contact_invalid_choice": "Por favor, ingrese un número de la lista anterior.",
        "contact_intake_complete": "Gracias! Su información ha sido recibida. Pronto nos comunicaremos con usted.",
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
