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
            "/comfort: Share what's on your heart and receive an encouraging Bible passage\n"
            "/contact: Reach a parish staff member\n"
            "/help: List available commands\n"
            "/schedules: View Mass and Confession times\n"
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
        "contact_intake_complete": "Thank you! We have received your information.",
        "contact_confirm_summary_header": "Here is a summary of your request:",
        "contact_confirm_prompt": (
            "Does this look right? Reply Yes to send, or No to cancel."
        ),
        "contact_confirm_re_ask": (
            "Please reply Yes to send your request, or No to cancel."
        ),
        "contact_confirm_success": (
            "Your request has been sent. "
            "A member of our parish staff will be in touch with you soon."
        ),
        "contact_confirm_send_error": (
            "Something went wrong sending your request. "
            "Please try replying Yes again, or type /cancel to start over."
        ),
        "contact_confirm_send_error_with_phone": (
            "Something went wrong sending your request. Please try replying Yes again."
            "If the problem persists, call the parish office directly at {phone} or type /cancel to start over."
        ),
        "comfort_intro": (
            "Welcome to /comfort.\n"
            "\n"
            "Share what's on your heart and I will find a Bible verse from our parish's "
            "curated list, along with a brief reflection. You can ask for another verse anytime.\n"
            "\n"
            "We care about your privacy so we don't store any personal or identifiable information, "
            "only a history of passages shared to avoid repeating them.\n"
            "\n"
            "If you are going through something difficult or seek frequent guidance, a priest or "
            "staff member may reach out to talk.\n"
            "\n"
            "Ready when you are."
        ),
        "comfort_brief_intro": "Share what's on your heart (3 paragraphs or less).",
        "comfort_input_too_long": (
            "Thank you for sharing. Your message is a bit long for me to process. Would you "
            "please shorten it to less than 2000 characters and send it again?"
        ),
        "comfort_ack_placeholder": (
            "This feature is still being built, so I can't offer a passage "
            "yet. Please check back soon."
        ),
        "comfort_crisis_message": (
            "Thank you for trusting me with your situation.\n"
            "If you don't mind, a priest from our parish may reach out to offer support. You are not alone in this.\n"
            "\n"
        ),
        "comfort_button_continue": "Continue",
        "comfort_crisis_email_subject": "Parish Companion: Urgent — /comfort crisis flag",
        "comfort_crisis_email_body": (
            "A parishioner's message through /comfort was flagged as describing a possible "
            "crisis (self-harm, suicidal ideation, sexual abuse, or physical violence).\n\n"
            "Telegram user ID: {telegram_user_id}\n\n"
            "Please follow up with this parishioner as soon as possible."
        ),
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
            "/contacto: Contactar personal de la parroquia\n"
            "/horarios: Horarios de Misa y Confesiones\n"
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
        "contact_intake_complete": "Gracias! Su información ha sido recibida.",
        "contact_confirm_summary_header": "Aquí está un resumen de su solicitud:",
        "contact_confirm_prompt": (
            "¿Es correcto? Responda Sí para enviar, o No para cancelar."
        ),
        "contact_confirm_re_ask": (
            "Por favor, responda Sí para enviar su solicitud, o No para cancelar."
        ),
        "contact_confirm_success": (
            "Su solicitud ha sido enviada."
            "Un miembro del personal de la parroquia se pondrá en contacto con usted pronto."
        ),
        "contact_confirm_send_error": (
            "Algo salió mal al enviar su solicitud. "
            "Intente respondiendo Sí nuevamente, o escriba /cancel para empezar de nuevo."
        ),
        "contact_confirm_send_error_with_phone": (
            "Algo salió mal enviando su solicitud. Por favor, intente respondiendo Sí nuevamente."
            "Si el problema persiste, llame a la parroquia directamente al {phone} o escriba /cancel para empezar de nuevo."
        ),
        "comfort_intro": (
            "Bienvenido a /comfort.\n"
            "\n"
            "Comparta lo que lleva en el corazón y yo trataré de ayudarle con un versículo bíblico de la lista "
            "seleccionada por nuestra parroquia, junto con una breve reflexión. Puede pedir otro "
            "versículo en cualquier momento.\n"
            "\n"
            "Nos importa su privacidad, por eso no guardamos ninguna información personal o identificable, "
            "solo un historial de los pasajes compartidos para evitar repetirlos.\n"
            "\n"
            "Si está atravesando algo difícil o busca orientación con frecuencia, un sacerdote o "
            "miembro del personal podría comunicarse con usted.\n"
            "\n"
            "Si gusta, podemos comenzar."
        ),
        "comfort_brief_intro": "Comparta lo que lleva en el corazón.",
        "comfort_input_too_long": (
            "Gracias por compartir. Su mensaje es un poco extenso para que yo pueda procesarlo. "
            "¿Podría reducirlo a menos de 2000 caracteres y enviarlo de nuevo?"
        ),
        "comfort_ack_placeholder": (
            "Esta función todavía está en desarrollo, así que todavía no "
            "puedo ofrecer un pasaje. Vuelva pronto, por favor."
        ),
        "comfort_crisis_message": (
            "Gracias por confiarme tu situación.\n"
            "Si estás de acuerdo, un sacerdote de nuestra parroquia podría comunicarse con vos para ofrecerte apoyo. Recuerda que no estás solo(a) en esto.\n"
            "\n"
        ),
        "comfort_button_continue": "Continuar",
        "comfort_crisis_email_subject": "Parish Companion: Urgente — alerta de crisis en /consolar",
        "comfort_crisis_email_body": (
            "El mensaje de un feligrés a través de /consolar fue marcado como una posible "
            "crisis (autolesión, ideación suicida, abuso sexual o violencia física).\n\n"
            "ID de usuario de Telegram: {telegram_user_id}\n\n"
            "Por favor, comuníquese con este feligrés lo antes posible."
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
