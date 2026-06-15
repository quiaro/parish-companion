from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from tests.conftest import TEST_SECRET
from translations import STRINGS

_CHAT_ID = 42

_headers = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}


def _command_update(command: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": _CHAT_ID, "type": "private"},
            "date": 1_700_000_000,
            "text": command,
        },
    }


# --- English commands --------------------------------------------------------

def test_start_sends_english_welcome(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/start"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_start"])


def test_help_sends_english_help(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_help"])


# --- Spanish commands --------------------------------------------------------

def test_inicio_sends_spanish_welcome(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/inicio"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["telegram_cmd_start"])


def test_ayuda_sends_spanish_help(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/ayuda"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["telegram_cmd_help"])


# --- Language is forced regardless of the user's detected language -----------

def test_help_is_always_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_help"])


def test_ayuda_is_always_spanish_even_when_session_language_is_english(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="en")):
        resp = client.post("/telegram/webhook", json=_command_update("/ayuda"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["telegram_cmd_help"])

