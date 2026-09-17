"""Router/webhook-level tests for /contact — covers the parts of the flow that only
show up once it's wired through telegram.router (button dispatch, notifier wiring on
app.state), as opposed to test_contact_flow.py which exercises commands.contact.flow
directly."""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import config
from commands.contact import flow as contact_flow
from main import app as fastapi_app
from telegram import commands
from tests.conftest import TEST_SECRET
from translations import get_start_message, get_string

_CHAT_ID = 42
_USER_ID = 99

_headers = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}

_REQUEST_TYPES_EN = '["Speak with a priest", "Spiritual director", "General question"]'
_REQUEST_TYPES_ES = '["Hablar con un sacerdote", "Director espiritual", "Pregunta general"]'


@pytest.fixture
def configured_types(monkeypatch):
    monkeypatch.setattr(config.settings, "contact_request_types", _REQUEST_TYPES_EN)
    monkeypatch.setattr(config.settings, "contact_request_types_es", _REQUEST_TYPES_ES)


@pytest.fixture
def contact_notifier_mock():
    mock = MagicMock()
    mock.send.return_value = True
    fastapi_app.state.contact_notifier = mock
    return mock


@pytest.fixture
def flow_store(monkeypatch):
    store: dict[str, dict] = {}

    async def mock_get(sid):
        return copy.deepcopy(store.get(sid))

    async def mock_set(sid, state):
        store[sid] = copy.deepcopy(state)

    async def mock_clear(sid):
        store.pop(sid, None)

    monkeypatch.setattr(contact_flow, "_get_state", mock_get)
    monkeypatch.setattr(contact_flow, "_set_state", mock_set)
    monkeypatch.setattr(contact_flow, "_clear_state", mock_clear)
    return store


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


def _callback_update(data: str, callback_id: str = "cb1") -> dict:
    return {
        "update_id": 3,
        "callback_query": {
            "id": callback_id,
            "from": {"id": _USER_ID, "is_bot": False, "first_name": "Jane"},
            "message": {
                "message_id": 3,
                "chat": {"id": _CHAT_ID, "type": "private"},
                "date": 1_700_000_002,
                "text": "placeholder",
            },
            "data": data,
        },
    }


def _advance_to_confirm(client: TestClient) -> None:
    client.post("/telegram/webhook", json=_command_update("/contact"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("Alice"), headers=_headers)
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        client.post(
            "/telegram/webhook",
            json=_callback_update(contact_flow._request_type_callback(0)),
            headers=_headers,
        )
    client.post("/telegram/webhook", json=_text_message("I need help with baptism."), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("Weekday evenings"), headers=_headers)


def test_confirmation_step_shows_send_and_cancel_buttons(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    _advance_to_confirm(client)

    assert mock_send.await_args is not None
    assert mock_send.await_args.kwargs["buttons"] == [
        (get_string("contact_button_send", "en"), contact_flow._CALLBACK_SEND),
        (get_string("contact_button_cancel", "en"), contact_flow._CALLBACK_CANCEL),
    ]


def test_tapping_send_calls_notifier_and_sends_success_then_help(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    _advance_to_confirm(client)
    mock_send.reset_mock()

    with patch("telegram.router.answer_callback_query", AsyncMock()) as answer_mock:
        resp = client.post(
            "/telegram/webhook", json=_callback_update(contact_flow._CALLBACK_SEND), headers=_headers
        )
        assert resp.status_code == 200
        answer_mock.assert_awaited_once_with("cb1")

    contact_notifier_mock.send.assert_called_once()
    assert mock_send.await_count == 2
    assert mock_send.await_args_list[0][0][1] == get_string("contact_confirm_success", "en")
    assert mock_send.await_args_list[1][0][1] == commands.build_help_reply("en")


def test_tapping_cancel_sends_cancellation_then_help_and_ends_flow(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    _advance_to_confirm(client)
    mock_send.reset_mock()

    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post(
            "/telegram/webhook", json=_callback_update(contact_flow._CALLBACK_CANCEL), headers=_headers
        )
        assert resp.status_code == 200

    contact_notifier_mock.send.assert_not_called()
    assert mock_send.await_count == 2
    assert mock_send.await_args_list[0][0][1] == get_string("contact_cancelled", "en")
    assert mock_send.await_args_list[1][0][1] == commands.build_help_reply("en")

    mock_send.reset_mock()
    resp2 = client.post("/telegram/webhook", json=_text_message("hello"), headers=_headers)
    assert resp2.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_start_message("en")


def test_send_failure_shows_error_without_help_followup(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    contact_notifier_mock.send.return_value = False
    _advance_to_confirm(client)
    mock_send.reset_mock()

    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post(
            "/telegram/webhook", json=_callback_update(contact_flow._CALLBACK_SEND), headers=_headers
        )
        assert resp.status_code == 200

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("contact_confirm_send_error", "en")


def test_text_at_confirm_step_is_silently_ignored(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    _advance_to_confirm(client)
    mock_send.reset_mock()

    resp = client.post("/telegram/webhook", json=_text_message("yes"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_not_awaited()


def test_request_type_step_shows_buttons(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/contact"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("Alice"), headers=_headers)

    assert mock_send.await_args is not None
    assert mock_send.await_args.kwargs["button_rows"] == [
        [("Speak with a priest", contact_flow._request_type_callback(0))],
        [("Spiritual director", contact_flow._request_type_callback(1))],
        [("General question", contact_flow._request_type_callback(2))],
    ]


def test_text_at_request_type_step_is_silently_ignored(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/contact"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("Alice"), headers=_headers)
    mock_send.reset_mock()

    resp = client.post("/telegram/webhook", json=_text_message("1"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_not_awaited()


def test_tapping_request_type_button_advances_to_message_question(
    client: TestClient, mock_send: AsyncMock, configured_types, contact_notifier_mock, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/contact"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("Alice"), headers=_headers)
    mock_send.reset_mock()

    with patch("telegram.router.answer_callback_query", AsyncMock()) as answer_mock:
        resp = client.post(
            "/telegram/webhook",
            json=_callback_update(contact_flow._request_type_callback(1)),
            headers=_headers,
        )
        assert resp.status_code == 200
        answer_mock.assert_awaited_once_with("cb1")

    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("contact_ask_message", "en")
    assert mock_send.await_args.kwargs.get("buttons") is None
    assert mock_send.await_args.kwargs.get("button_rows") is None
