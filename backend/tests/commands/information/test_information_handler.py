from unittest.mock import MagicMock

from commands.information.models import InformationTopic
from telegram import information
from translations import get_string


def _topic(**overrides) -> InformationTopic:
    defaults = dict(key="mass_times", label_en="Mass Times", body_en="Sundays at 9am.", order=1)
    defaults.update(overrides)
    return InformationTopic(**defaults)  # type: ignore[arg-type]


def _adapter(
    topics: list[InformationTopic] | None = None, get_topic_result: InformationTopic | None = None
) -> MagicMock:
    adapter = MagicMock()
    adapter.list_topics.return_value = topics or []
    adapter.get_topic.return_value = get_topic_result
    return adapter


class TestTopicCallback:
    def test_encodes_the_topic_key(self):
        assert information._topic_callback("mass_times") == "info|topic|mass_times"


class TestMenuCallback:
    def test_encodes_the_menu_action(self):
        assert information._menu_callback() == "info|menu"


class TestParseCallback:
    def test_topic_callback_round_trips(self):
        assert information.parse_callback("info|topic|mass_times") == ("topic", "mass_times")

    def test_menu_callback_round_trips(self):
        assert information.parse_callback("info|menu") == ("menu", None)

    def test_topic_key_containing_pipe_returns_none(self):
        # Malformed callback_data (not a real key this feature would ever generate) 
        # should fail closed, not crash.
        assert information.parse_callback("info|topic|weird|key") is None

    def test_unrelated_callback_data_returns_none(self):
        assert information.parse_callback("comfort_view_another") is None

    def test_topic_action_without_a_key_returns_none(self):
        assert information.parse_callback("info|topic") is None

    def test_unknown_action_returns_none(self):
        assert information.parse_callback("info|unknown") is None


class TestHandleCommand:
    def test_intro_text_is_localized(self):
        topics = [_topic(key="a", order=1)]
        reply = information.handle_command(_adapter(topics), "es")
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

    def test_shows_apology_message_with_no_buttons_when_there_are_no_topics(self):
        reply = information.handle_command(_adapter([]), "en")
        assert reply.text == get_string("information_empty", "en")
        assert reply.button_rows is None

    def test_apology_message_is_localized(self):
        reply = information.handle_command(_adapter([]), "es")
        assert reply.text == get_string("information_empty", "es")


class TestHandleTopicSelection:
    def test_fetches_by_key(self):
        adapter = _adapter(get_topic_result=_topic(key="mass_times"))
        information.handle_topic_selection(adapter, "mass_times")
        adapter.get_topic.assert_called_once_with("mass_times")

    def test_shows_body_en(self):
        topic = _topic(body_en="Sundays at 9am.")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "mass_times")
        assert reply is not None
        assert reply.text == "Sundays at 9am."

    def test_markdown_in_body_passes_through_unmodified(self):
        topic = _topic(body_en="*Sundays* at [9am](https://example.com).")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "mass_times")
        assert reply is not None
        assert reply.text == "*Sundays* at [9am](https://example.com)."

    def test_includes_a_back_to_menu_button(self):
        reply = information.handle_topic_selection(_adapter(get_topic_result=_topic()), "mass_times")
        assert reply is not None
        assert reply.button_rows == [
            [(get_string("information_button_back", "en"), "info|menu")]
        ]

    def test_returns_none_when_topic_does_not_exist(self):
        reply = information.handle_topic_selection(_adapter(get_topic_result=None), "missing")
        assert reply is None
