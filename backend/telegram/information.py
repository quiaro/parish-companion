from translations import get_string


def handle_command(language: str) -> str:
    return get_string("information_ack_placeholder", language)
