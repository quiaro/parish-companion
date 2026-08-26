import logging
from dataclasses import dataclass
from typing import Optional

from commands.information.adapter import InformationAdapter
from commands.information.models import InformationTopic, InformationUnavailableError
from translations import get_string

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "info"
TOPIC_ACTION = "topic"
MENU_ACTION = "menu"


@dataclass
class InformationReply:
    text: str
    button_rows: Optional[list[list[tuple[str, str]]]] = None


def _topic_callback(language: str, key: str) -> str:
    return f"{CALLBACK_PREFIX}|{language}|{TOPIC_ACTION}|{key}"


def _menu_callback(language: str) -> str:
    return f"{CALLBACK_PREFIX}|{language}|{MENU_ACTION}"


def parse_callback(data: str) -> Optional[tuple[str, str, Optional[str]]]:
    """Returns (language, action, key) for a recognized /information callback, or None
    if data doesn't belong to this feature. key is only present for TOPIC_ACTION."""
    parts = data.split("|")
    if len(parts) < 3 or parts[0] != CALLBACK_PREFIX:
        return None
    language, action = parts[1], parts[2]
    if action == MENU_ACTION and len(parts) == 3:
        return language, MENU_ACTION, None
    if action == TOPIC_ACTION and len(parts) == 4:
        return language, TOPIC_ACTION, parts[3]
    return None


def _topic_label(topic: InformationTopic, language: str) -> str:
    return topic.label_es if language == "es" else topic.label_en


def handle_command(adapter: InformationAdapter, language: str) -> InformationReply:
    try:
        topics = adapter.list_topics()
    except InformationUnavailableError:
        # The adapter logs the failure with debugging detail.
        return InformationReply(text=get_string("information_unavailable", language))

    if language == "es":
        translated, untranslated = [], []
        for topic in topics:
            (translated if topic.label_es else untranslated).append(topic)
        for topic in untranslated:
            logger.error(
                "Information topic %r has no Spanish label (label_es is empty)."
                "It is hidden from /información until an admin adds one",
                topic.key,
            )
        topics = translated

    if not topics:
        return InformationReply(text=get_string("information_empty", language))
    button_rows = [[(_topic_label(t, language), _topic_callback(language, t.key))] for t in topics]
    return InformationReply(text=get_string("information_menu_intro", language), button_rows=button_rows)


def handle_topic_selection(adapter: InformationAdapter, language: str, key: str) -> Optional[InformationReply]:
    """Returns None if the topic no longer exists (e.g. removed from the sheet since
    the menu was rendered); the router sends nothing in that case."""
    try:
        topic = adapter.get_topic(key)
    except InformationUnavailableError:
        return InformationReply(text=get_string("information_unavailable", language))
    if topic is None:
        return None

    if language == "es":
        if not topic.body_es:
            logger.error(
                "Information topic %r has no Spanish content (body_es is empty) — "
                "an admin needs to add one",
                topic.key,
            )
            text = get_string("information_es_unavailable", "es")
        else:
            text = topic.body_es
    else:
        text = topic.body_en

    back_row = [(get_string("information_button_back", language), _menu_callback(language))]
    return InformationReply(text=text, button_rows=[back_row])
