import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from commands.comfort import flow
from tests.conftest import TEST_SECRET
from translations import get_string

_CHAT_ID = 42
_USER_ID = 99

_headers = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}


def _command_update(command: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": _CHAT_ID, "type": "private"},
            "from": {"id": _USER_ID, "is_bot": False, "first_name": "Jane"},
            "date": 1_700_000_000,
            "text": command,
        },
    }


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


def test_comfort_command_sends_full_intro_on_first_use(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    assert resp.status_code == 200
    db_mocks["mark_comfort_intro_shown"].assert_called_once_with(_USER_ID)

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_intro", "en")


def test_comfort_command_sends_brief_prompt_on_subsequent_use(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    db_mocks["is_comfort_intro_shown"].return_value = True
    resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    assert resp.status_code == 200
    db_mocks["mark_comfort_intro_shown"].assert_not_called()

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_prompt_brief", "en")


def test_comfort_command_always_replies_in_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    db_mocks["is_comfort_intro_shown"].return_value = True
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
        assert resp.status_code == 200

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_prompt_brief", "en")


def _text_message(text: str) -> dict:
    return {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "chat": {"id": _CHAT_ID, "type": "private"},
            "from": {"id": _USER_ID, "is_bot": False, "first_name": "Jane"},
            "date": 1_700_000_001,
            "text": text,
        },
    }


def test_free_text_after_comfort_command_returns_placeholder_ack(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    resp = client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)
    assert resp.status_code == 200

    assert mock_send.await_count == 2
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_ack_placeholder", "en")


def test_overlong_free_text_gets_gentle_reprompt_and_can_be_resubmitted(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("a" * 2001), headers=_headers)
    assert mock_send.await_args is not None
    too_long_reply = mock_send.await_args[0][1]
    assert too_long_reply == get_string("comfort_input_too_long", "en")

    client.post("/telegram/webhook", json=_text_message("a shorter message"), headers=_headers)
    assert mock_send.await_args is not None
    final_reply = mock_send.await_args[0][1]
    assert final_reply == get_string("comfort_ack_placeholder", "en")
