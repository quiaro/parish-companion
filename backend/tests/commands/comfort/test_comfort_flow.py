"""Tests for the /comfort flow (K-01, K-02) — independent of the Telegram layer."""

import copy
from unittest.mock import MagicMock

import pytest

from commands.comfort import flow
from translations import get_string

_SESSION = "session_abc"
_UID = 555666777


@pytest.fixture
def db_mocks(monkeypatch):
    mocks = {
        "ensure_parishioner": MagicMock(),
        "is_comfort_intro_shown": MagicMock(return_value=False),
        "mark_comfort_intro_shown": MagicMock(),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(flow, name, mock)
    return mocks


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


class TestStart:
    @pytest.mark.asyncio
    async def test_first_use_sends_full_intro(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        reply = await flow.start(_SESSION, _UID, "en")
        assert reply == get_string("comfort_intro", "en")

    @pytest.mark.asyncio
    async def test_first_use_marks_intro_shown(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        await flow.start(_SESSION, _UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_use_calls_ensure_parishioner(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        db_mocks["ensure_parishioner"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_subsequent_use_sends_brief_prompt(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_SESSION, _UID, "en")
        assert reply == get_string("comfort_prompt_brief", "en")

    @pytest.mark.asyncio
    async def test_subsequent_use_does_not_remark_intro_shown(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        await flow.start(_SESSION, _UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_language_argument(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_SESSION, _UID, "es")
        assert reply == get_string("comfort_prompt_brief", "es")

    @pytest.mark.asyncio
    async def test_stores_flow_state_for_the_session(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        assert flow_store[_SESSION] == {"language": "en", "telegram_user_id": _UID}


class TestHandleText:
    @pytest.mark.asyncio
    async def test_within_limit_returns_placeholder_ack(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_within_limit_clears_flow_state(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "A single word is enough.")
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_exactly_2000_characters_is_accepted(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2000)
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_2001_characters_is_rejected_with_gentle_reprompt(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply == get_string("comfort_input_too_long", "en")

    @pytest.mark.asyncio
    async def test_too_long_submission_keeps_flow_state_for_a_retry(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "a" * 2001)
        assert _SESSION in flow_store

    @pytest.mark.asyncio
    async def test_can_resubmit_after_a_too_long_message(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "a" * 2001)
        reply = await flow.handle_text(_SESSION, "a shorter message")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_length_check_uses_stripped_text(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "  " + "a" * 2000 + "  ")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_respects_stored_session_language(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "es")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply == get_string("comfort_input_too_long", "es")

    @pytest.mark.asyncio
    async def test_no_active_flow_returns_unknown_command_fallback(self, flow_store) -> None:
        reply = await flow.handle_text(_SESSION, "hello")
        assert reply == get_string("telegram_cmd_unknown", "en")
