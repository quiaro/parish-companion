from dataclasses import dataclass
from typing import Optional

from commands.information.adapter import InformationAdapter
from translations import get_string


@dataclass
class InformationReply:
    text: str
    button_rows: Optional[list[list[tuple[str, str]]]] = None


def _topic_callback(key: str) -> str:
    return f"info|topic|{key}"


def handle_command(adapter: InformationAdapter, language: str) -> InformationReply:
    topics = adapter.list_topics()
    button_rows = [[(t.label_en, _topic_callback(t.key))] for t in topics] or None
    return InformationReply(text=get_string("information_menu_intro", language), button_rows=button_rows)
