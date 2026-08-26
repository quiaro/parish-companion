from dataclasses import dataclass
from typing import Optional

from commands.information.adapter import InformationAdapter
from commands.information.models import InformationUnavailableError
from translations import get_string

CALLBACK_PREFIX = "info"
TOPIC_ACTION = "topic"
MENU_ACTION = "menu"


@dataclass
class InformationReply:
    text: str
    button_rows: Optional[list[list[tuple[str, str]]]] = None


def _topic_callback(key: str) -> str:
    return f"{CALLBACK_PREFIX}|{TOPIC_ACTION}|{key}"


def _menu_callback() -> str:
    return f"{CALLBACK_PREFIX}|{MENU_ACTION}"


def parse_callback(data: str) -> Optional[tuple[str, Optional[str]]]:
    """Returns (action, key) for a recognized /information callback, or None if data
    doesn't belong to this feature. key is only present for TOPIC_ACTION."""
    parts = data.split("|")
    if len(parts) < 2 or parts[0] != CALLBACK_PREFIX:
        return None
    action = parts[1]
    if action == MENU_ACTION:
        return MENU_ACTION, None
    if action == TOPIC_ACTION and len(parts) == 3:
        return TOPIC_ACTION, parts[2]
    return None


def handle_command(adapter: InformationAdapter, language: str) -> InformationReply:
    try:
        topics = adapter.list_topics()
    except InformationUnavailableError:
        # The adapter logs the failure with debugging detail.
        return InformationReply(text=get_string("information_unavailable", language))
    if not topics:
        return InformationReply(text=get_string("information_empty", language))
    button_rows = [[(t.label_en, _topic_callback(t.key))] for t in topics]
    return InformationReply(text=get_string("information_menu_intro", language), button_rows=button_rows)


def handle_topic_selection(adapter: InformationAdapter, key: str) -> Optional[InformationReply]:
    """Returns None if the topic no longer exists (e.g. removed from the sheet since
    the menu was rendered); the router sends nothing in that case."""
    try:
        topic = adapter.get_topic(key)
    except InformationUnavailableError:
        return InformationReply(text=get_string("information_unavailable", "en"))
    if topic is None:
        return None
    # English-only for now, matching I-04's body_en/label_en scope — I-09 localizes
    # this entry point (including this button) for /información.
    back_row = [(get_string("information_button_back", "en"), _menu_callback())]
    return InformationReply(text=topic.body_en, button_rows=[back_row])
