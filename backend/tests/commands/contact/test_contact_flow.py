"""Tests for the contact intake flow — independent of the Telegram layer."""

import copy

import pytest

from commands.contact import flow
from translations import get_string

_SESSION = "session_abc"
_REQUEST_TYPES_EN = '["Speak with a priest", "Spiritual director", "General question"]'
_REQUEST_TYPES_ES = '["Hablar con un sacerdote", "Director espiritual", "Pregunta general"]'


@pytest.fixture
def flow_store(monkeypatch):
    store: dict[str, dict] = {}

    async def mock_get(sid):
        return copy.deepcopy(store.get(sid))

    async def mock_set(sid, state):
        store[sid] = copy.deepcopy(state)

    async def mock_clear(sid):
        store.pop(sid, None)

    monkeypatch.setattr(flow, "_get_state", mock_get)
    monkeypatch.setattr(flow, "_set_state", mock_set)
    monkeypatch.setattr(flow, "_clear_state", mock_clear)
    return store


@pytest.fixture
def configured_types(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "contact_request_types", _REQUEST_TYPES_EN)
    monkeypatch.setattr(config.settings, "contact_request_types_es", _REQUEST_TYPES_ES)


class TestStart:
    @pytest.mark.asyncio
    async def test_initialises_step_to_name(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        assert flow_store[_SESSION]["step"] == "name"

    @pytest.mark.asyncio
    async def test_stores_language(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        assert flow_store[_SESSION]["language"] == "es"

    @pytest.mark.asyncio
    async def test_returns_name_question(self, flow_store, configured_types) -> None:
        reply = await flow.start(_SESSION, "en")
        assert reply == get_string("contact_ask_name", "en")

    @pytest.mark.asyncio
    async def test_resets_existing_flow(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        await flow.start(_SESSION, "en")
        assert flow_store[_SESSION]["step"] == "name"
        assert flow_store[_SESSION]["answers"] == {}


class TestAdvance:
    @pytest.mark.asyncio
    async def test_name_answer_records_value_and_advances(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        reply, done = await flow.advance(_SESSION, "Alice")
        assert flow_store[_SESSION]["answers"]["name"] == "Alice"
        assert flow_store[_SESSION]["step"] == "request_type"
        assert not done

    @pytest.mark.asyncio
    async def test_name_answer_strips_whitespace(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "  Alice  ")
        assert flow_store[_SESSION]["answers"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_request_type_valid_number_records_label(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        await flow.advance(_SESSION, "2")
        assert flow_store[_SESSION]["answers"]["request_type"] == "Spiritual director"
        assert flow_store[_SESSION]["step"] == "message"

    @pytest.mark.asyncio
    async def test_request_type_first_option(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        reply, done = await flow.advance(_SESSION, "1")
        assert flow_store[_SESSION]["answers"]["request_type"] == "Speak with a priest"
        assert not done

    @pytest.mark.asyncio
    async def test_request_type_invalid_text_stays_on_step(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        reply, done = await flow.advance(_SESSION, "not a number")
        assert flow_store[_SESSION]["step"] == "request_type"
        assert not done

    @pytest.mark.asyncio
    async def test_request_type_out_of_range_stays_on_step(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        reply, done = await flow.advance(_SESSION, "99")
        assert flow_store[_SESSION]["step"] == "request_type"
        assert not done

    @pytest.mark.asyncio
    async def test_request_type_invalid_reply_contains_error_hint(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        reply, _ = await flow.advance(_SESSION, "banana")
        assert get_string("contact_invalid_choice", "en") in reply

    @pytest.mark.asyncio
    async def test_message_answer_advances_to_preferred_time(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        await flow.advance(_SESSION, "1")
        reply, done = await flow.advance(_SESSION, "I need help with baptism.")
        assert flow_store[_SESSION]["step"] == "preferred_time"
        assert not done

    @pytest.mark.asyncio
    async def test_preferred_time_completes_flow(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        await flow.advance(_SESSION, "1")
        await flow.advance(_SESSION, "I need help with baptism.")
        reply, done = await flow.advance(_SESSION, "Weekday evenings")
        assert done
        assert flow_store[_SESSION]["step"] == "done"
        assert get_string("contact_intake_complete", "en") in reply

    @pytest.mark.asyncio
    async def test_completed_state_holds_all_answers(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.advance(_SESSION, "Alice")
        await flow.advance(_SESSION, "3")
        await flow.advance(_SESSION, "I need help with baptism.")
        await flow.advance(_SESSION, "Weekday evenings")
        answers = flow_store[_SESSION]["answers"]
        assert answers["name"] == "Alice"
        assert answers["request_type"] == "General question"
        assert answers["message"] == "I need help with baptism."
        assert answers["preferred_time"] == "Weekday evenings"

    @pytest.mark.asyncio
    async def test_done_step_returns_done_true(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        flow_store[_SESSION]["step"] = "done"
        reply, done = await flow.advance(_SESSION, "anything")
        assert done
        assert get_string("contact_intake_complete", "en") in reply


class TestCancel:
    @pytest.mark.asyncio
    async def test_clears_state(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        await flow.cancel(_SESSION)
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_returns_non_empty_message(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        reply = await flow.cancel(_SESSION)
        assert reply

    @pytest.mark.asyncio
    async def test_uses_flow_language(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        reply = await flow.cancel(_SESSION)
        assert reply == get_string("contact_cancelled", "es")

    @pytest.mark.asyncio
    async def test_cancel_with_no_active_flow_defaults_to_english(self, flow_store) -> None:
        reply = await flow.cancel(_SESSION)
        assert reply == get_string("contact_cancelled", "en")


class TestGetState:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_flow_active(self, flow_store) -> None:
        assert await flow.get_state(_SESSION) is None

    @pytest.mark.asyncio
    async def test_returns_state_when_flow_active(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "en")
        state = await flow.get_state(_SESSION)
        assert state is not None
        assert state["step"] == "name"


def _make_notifier(send_returns: bool = True):
    from unittest.mock import MagicMock
    notifier = MagicMock()
    notifier.send.return_value = send_returns
    return notifier


async def _advance_to_done() -> None:
    """Drive the English flow to the done step (answers collected, before confirmation prompt)."""
    await flow.start(_SESSION, "en")
    await flow.advance(_SESSION, "Alice")
    await flow.advance(_SESSION, "1")
    await flow.advance(_SESSION, "I need help with baptism.")
    _, done = await flow.advance(_SESSION, "Weekday evenings")
    assert done


async def _advance_to_confirm() -> None:
    """Drive the English flow to the confirm step."""
    await _advance_to_done()
    await flow.present_confirmation(_SESSION)


class TestPresentConfirmation:
    @pytest.mark.asyncio
    async def test_transitions_step_to_confirm(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        assert flow_store[_SESSION]["step"] == "confirm"

    @pytest.mark.asyncio
    async def test_reply_contains_all_answers(self, flow_store, configured_types) -> None:
        await _advance_to_done()
        reply = await flow.present_confirmation(_SESSION)
        assert "Alice" in reply
        assert "Speak with a priest" in reply
        assert "I need help with baptism." in reply
        assert "Weekday evenings" in reply

    @pytest.mark.asyncio
    async def test_reply_contains_confirm_prompt(self, flow_store, configured_types) -> None:
        await _advance_to_done()
        reply = await flow.present_confirmation(_SESSION)
        assert get_string("contact_confirm_prompt", "en") in reply

    @pytest.mark.asyncio
    async def test_uses_flow_language_for_labels(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        await flow.advance(_SESSION, "María")
        await flow.advance(_SESSION, "1")
        await flow.advance(_SESSION, "Necesito ayuda.")
        await flow.advance(_SESSION, "Por las tardes")
        reply = await flow.present_confirmation(_SESSION)
        assert get_string("contact_confirm_prompt", "es") in reply


class TestSubmit:
    @pytest.mark.asyncio
    async def test_yes_calls_notifier(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        notifier = _make_notifier()
        await flow.submit(_SESSION, "yes", notifier, 123, "alice")
        notifier.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_yes_builds_contact_request_correctly(self, flow_store, configured_types) -> None:
        from commands.contact.models import ContactRequest
        await _advance_to_confirm()
        notifier = _make_notifier()
        await flow.submit(_SESSION, "yes", notifier, 123, "alice")
        request: ContactRequest = notifier.send.call_args.args[0]
        assert request.name == "Alice"
        assert request.request_type == "Speak with a priest"
        assert request.message == "I need help with baptism."
        assert request.preferred_time == "Weekday evenings"
        assert request.telegram_user_id == 123
        assert request.telegram_username == "alice"
        assert request.language == "en"

    @pytest.mark.asyncio
    async def test_yes_clears_state_on_success(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        await flow.submit(_SESSION, "yes", _make_notifier(True), 123, None)
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_yes_returns_success_message(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        reply = await flow.submit(_SESSION, "yes", _make_notifier(True), 123, None)
        assert get_string("contact_confirm_success", "en") in reply

    @pytest.mark.asyncio
    async def test_y_accepted_as_yes(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        reply = await flow.submit(_SESSION, "y", _make_notifier(True), 123, None)
        assert get_string("contact_confirm_success", "en") in reply

    @pytest.mark.asyncio
    async def test_si_accepted_as_yes(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        await flow.advance(_SESSION, "María")
        await flow.advance(_SESSION, "1")
        await flow.advance(_SESSION, "Necesito ayuda.")
        await flow.advance(_SESSION, "Por las tardes")
        await flow.present_confirmation(_SESSION)
        reply = await flow.submit(_SESSION, "sí", _make_notifier(True), 123, None)
        assert get_string("contact_confirm_success", "es") in reply

    @pytest.mark.asyncio
    async def test_no_clears_state(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        await flow.submit(_SESSION, "no", _make_notifier(), 123, None)
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_no_returns_cancel_message(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        reply = await flow.submit(_SESSION, "no", _make_notifier(), 123, None)
        assert reply == get_string("contact_cancelled", "en")

    @pytest.mark.asyncio
    async def test_unrecognized_input_re_asks(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        reply = await flow.submit(_SESSION, "maybe", _make_notifier(), 123, None)
        assert get_string("contact_confirm_re_ask", "en") in reply

    @pytest.mark.asyncio
    async def test_unrecognized_input_keeps_state_at_confirm(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        assert flow_store[_SESSION]["step"] == "confirm"
        await flow.submit(_SESSION, "maybe", _make_notifier(), 123, None)
        assert flow_store[_SESSION]["step"] == "confirm"

    @pytest.mark.asyncio
    async def test_send_failure_keeps_state(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        assert flow_store[_SESSION]["step"] == "confirm"
        await flow.submit(_SESSION, "yes", _make_notifier(False), 123, None)
        assert _SESSION in flow_store
        assert flow_store[_SESSION]["step"] == "confirm"

    @pytest.mark.asyncio
    async def test_send_failure_returns_error_message(self, flow_store, configured_types) -> None:
        await _advance_to_confirm()
        reply = await flow.submit(_SESSION, "yes", _make_notifier(False), 123, None)
        assert get_string("contact_confirm_send_error", "en") in reply


class TestSpanishFlow:
    @pytest.mark.asyncio
    async def test_uses_spanish_request_types(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        await flow.advance(_SESSION, "María")
        await flow.advance(_SESSION, "2")
        assert flow_store[_SESSION]["answers"]["request_type"] == "Director espiritual"

    @pytest.mark.asyncio
    async def test_full_happy_path(self, flow_store, configured_types) -> None:
        await flow.start(_SESSION, "es")
        await flow.advance(_SESSION, "María")
        await flow.advance(_SESSION, "1")
        await flow.advance(_SESSION, "Necesito hablar con alguien.")
        reply, done = await flow.advance(_SESSION, "Por las tardes")
        assert done
        answers = flow_store[_SESSION]["answers"]
        assert answers["name"] == "María"
        assert answers["request_type"] == "Hablar con un sacerdote"
        assert answers["message"] == "Necesito hablar con alguien."
        assert answers["preferred_time"] == "Por las tardes"
