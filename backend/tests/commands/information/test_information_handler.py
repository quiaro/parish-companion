from unittest.mock import MagicMock

from commands.information.models import InformationTopic
from telegram import information
from translations import get_string


def _topic(**overrides) -> InformationTopic:
    defaults = dict(key="mass_times", label_en="Mass Times", body_en="Sundays at 9am.", order=1)
    defaults.update(overrides)
    return InformationTopic(**defaults)  # type: ignore[arg-type]


def _adapter(topics: list[InformationTopic] | None = None) -> MagicMock:
    adapter = MagicMock()
    adapter.list_topics.return_value = topics or []
    return adapter


class TestTopicCallback:
    def test_encodes_the_topic_key(self):
        assert information._topic_callback("mass_times") == "info|topic|mass_times"


class TestHandleCommand:
    def test_intro_text_is_localized(self):
        reply = information.handle_command(_adapter([]), "es")
        assert reply.text == get_string("information_menu_intro", "es")

    def test_one_button_row_per_topic_in_the_order_given(self):
        topics = [_topic(key="a", label_en="A", order=1), _topic(key="b", label_en="B", order=2)]
        reply = information.handle_command(_adapter(topics), "en")
        assert reply.button_rows == [
            [("A", "info|topic|a")],
            [("B", "info|topic|b")],
        ]

    def test_button_labels_use_label_en_regardless_of_language(self):
        # I-04 scope: labels stay English-only until I-09 adds Spanish localization.
        topics = [_topic(key="a", label_en="A", label_es="La A", order=1)]
        reply = information.handle_command(_adapter(topics), "es")
        assert reply.button_rows == [[("A", "info|topic|a")]]

    def test_no_button_rows_when_there_are_no_topics(self):
        reply = information.handle_command(_adapter([]), "en")
        assert reply.button_rows is None
