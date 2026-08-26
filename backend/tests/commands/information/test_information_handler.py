import logging
from unittest.mock import MagicMock

from commands.information.models import InformationTopic, InformationUnavailableError
from telegram import information
from translations import get_string


def _topic(**overrides) -> InformationTopic:
    defaults = dict(
        key="mass_times", label_en="Mass Times", label_es="Horarios de Misa",
        body_en="Sundays at 9am.", order=1,
    )
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
    def test_encodes_the_language_and_topic_key(self):
        assert information._topic_callback("en", "mass_times") == "info|en|topic|mass_times"


class TestMenuCallback:
    def test_encodes_the_language_and_menu_action(self):
        assert information._menu_callback("es") == "info|es|menu"


class TestParseCallback:
    def test_topic_callback_round_trips(self):
        assert information.parse_callback("info|en|topic|mass_times") == ("en", "topic", "mass_times")

    def test_menu_callback_round_trips(self):
        assert information.parse_callback("info|es|menu") == ("es", "menu", None)

    def test_topic_key_containing_pipe_returns_none(self):
        # Malformed callback_data (not a real key this feature would ever generate)
        # should fail closed, not crash.
        assert information.parse_callback("info|en|topic|weird|key") is None

    def test_unrelated_callback_data_returns_none(self):
        assert information.parse_callback("comfort_view_another") is None

    def test_topic_action_without_a_key_returns_none(self):
        assert information.parse_callback("info|en|topic") is None

    def test_unknown_action_returns_none(self):
        assert information.parse_callback("info|en|unknown") is None


class TestHandleCommand:
    def test_intro_text_is_localized(self):
        topics = [_topic(key="a", order=1)]
        reply = information.handle_command(_adapter(topics), "es")
        assert reply.text == get_string("information_menu_intro", "es")

    def test_one_button_row_per_topic_in_the_order_given(self):
        topics = [_topic(key="a", label_en="A", order=1), _topic(key="b", label_en="B", order=2)]
        reply = information.handle_command(_adapter(topics), "en")
        assert reply.button_rows == [
            [("A", "info|en|topic|a")],
            [("B", "info|en|topic|b")],
        ]

    def test_english_menu_uses_label_en(self):
        topics = [_topic(key="a", label_en="A", label_es="La A", order=1)]
        reply = information.handle_command(_adapter(topics), "en")
        assert reply.button_rows == [[("A", "info|en|topic|a")]]

    def test_spanish_menu_uses_label_es(self):
        topics = [_topic(key="a", label_en="A", label_es="La A", order=1)]
        reply = information.handle_command(_adapter(topics), "es")
        assert reply.button_rows == [[("La A", "info|es|topic|a")]]

    def test_topic_missing_label_es_is_hidden_from_spanish_menu(self):
        topics = [
            _topic(key="a", label_en="A", label_es="", order=1),
            _topic(key="b", label_en="B", label_es="La B", order=2),
        ]
        reply = information.handle_command(_adapter(topics), "es")
        assert reply.button_rows == [[("La B", "info|es|topic|b")]]

    def test_topic_missing_label_es_still_shown_in_english_menu(self):
        topics = [_topic(key="a", label_en="A", label_es="", order=1)]
        reply = information.handle_command(_adapter(topics), "en")
        assert reply.button_rows == [[("A", "info|en|topic|a")]]

    def test_missing_label_es_is_logged_as_an_error(self, caplog):
        topics = [_topic(key="a", label_en="A", label_es="", order=1)]
        with caplog.at_level(logging.ERROR, logger="telegram.information"):
            information.handle_command(_adapter(topics), "es")
        assert any("a" in message and "Spanish label" in message for message in caplog.messages)

    def test_shows_apology_when_all_topics_are_hidden_from_spanish_menu(self):
        topics = [_topic(key="a", label_en="A", label_es="", order=1)]
        reply = information.handle_command(_adapter(topics), "es")
        assert reply.text == get_string("information_empty", "es")
        assert reply.button_rows is None

    def test_shows_apology_message_with_no_buttons_when_there_are_no_topics(self):
        reply = information.handle_command(_adapter([]), "en")
        assert reply.text == get_string("information_empty", "en")
        assert reply.button_rows is None

    def test_apology_message_is_localized(self):
        reply = information.handle_command(_adapter([]), "es")
        assert reply.text == get_string("information_empty", "es")

    def test_shows_unavailable_message_with_no_buttons_when_fetch_fails(self):
        adapter = MagicMock()
        adapter.list_topics.side_effect = InformationUnavailableError("down")
        reply = information.handle_command(adapter, "en")
        assert reply.text == get_string("information_unavailable", "en")
        assert reply.button_rows is None

    def test_unavailable_message_is_localized(self):
        adapter = MagicMock()
        adapter.list_topics.side_effect = InformationUnavailableError("down")
        reply = information.handle_command(adapter, "es")
        assert reply.text == get_string("information_unavailable", "es")

    def test_unavailable_message_never_includes_raw_error_detail(self):
        adapter = MagicMock()
        adapter.list_topics.side_effect = InformationUnavailableError("secret internal detail")
        reply = information.handle_command(adapter, "en")
        assert "secret internal detail" not in reply.text


class TestHandleTopicSelection:
    def test_fetches_by_key(self):
        adapter = _adapter(get_topic_result=_topic(key="mass_times"))
        information.handle_topic_selection(adapter, "en", "mass_times")
        adapter.get_topic.assert_called_once_with("mass_times")

    def test_shows_body_en_in_english(self):
        topic = _topic(body_en="Sundays at 9am.")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "en", "mass_times")
        assert reply is not None
        assert reply.text == "Sundays at 9am."

    def test_shows_body_es_in_spanish(self):
        topic = _topic(body_en="Sundays.", body_es="Domingos.")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "es", "mass_times")
        assert reply is not None
        assert reply.text == "Domingos."

    def test_shows_placeholder_when_body_es_is_missing(self):
        topic = _topic(body_en="Sundays.", body_es="")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "es", "mass_times")
        assert reply is not None
        assert reply.text == get_string("information_es_unavailable", "es")
        assert reply.text != topic.body_en

    def test_missing_body_es_is_logged_as_an_error(self, caplog):
        topic = _topic(key="mass_times", body_en="Sundays.", body_es="")
        with caplog.at_level(logging.ERROR, logger="telegram.information"):
            information.handle_topic_selection(_adapter(get_topic_result=topic), "es", "mass_times")
        assert any("mass_times" in message and "Spanish content" in message for message in caplog.messages)

    def test_markdown_in_body_passes_through_unmodified(self):
        topic = _topic(body_en="*Sundays* at [9am](https://example.com).")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "en", "mass_times")
        assert reply is not None
        assert reply.text == "*Sundays* at [9am](https://example.com)."

    def test_includes_a_back_to_menu_button_in_english(self):
        reply = information.handle_topic_selection(_adapter(get_topic_result=_topic()), "en", "mass_times")
        assert reply is not None
        assert reply.button_rows == [
            [(get_string("information_button_back", "en"), "info|en|menu")]
        ]

    def test_includes_a_back_to_menu_button_in_spanish(self):
        topic = _topic(body_es="Domingos.")
        reply = information.handle_topic_selection(_adapter(get_topic_result=topic), "es", "mass_times")
        assert reply is not None
        assert reply.button_rows == [
            [(get_string("information_button_back", "es"), "info|es|menu")]
        ]

    def test_returns_none_when_topic_does_not_exist(self):
        reply = information.handle_topic_selection(_adapter(get_topic_result=None), "en", "missing")
        assert reply is None

    def test_shows_unavailable_message_with_no_buttons_when_fetch_fails(self):
        adapter = MagicMock()
        adapter.get_topic.side_effect = InformationUnavailableError("down")
        reply = information.handle_topic_selection(adapter, "en", "mass_times")
        assert reply is not None
        assert reply.text == get_string("information_unavailable", "en")
        assert reply.button_rows is None

    def test_unavailable_message_is_localized(self):
        adapter = MagicMock()
        adapter.get_topic.side_effect = InformationUnavailableError("down")
        reply = information.handle_topic_selection(adapter, "es", "mass_times")
        assert reply is not None
        assert reply.text == get_string("information_unavailable", "es")

    def test_unavailable_message_never_includes_raw_error_detail(self):
        adapter = MagicMock()
        adapter.get_topic.side_effect = InformationUnavailableError("secret internal detail")
        reply = information.handle_topic_selection(adapter, "en", "mass_times")
        assert reply is not None
        assert "secret internal detail" not in reply.text
