from unittest.mock import AsyncMock

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


def test_start_sends_welcome(client: TestClient, mock_send: AsyncMock) -> None:
    """AC1: /start returns welcome message listing supported topics."""
    resp = client.post("/telegram/webhook", json=_command_update("/start"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_start"])


def test_help_sends_help(client: TestClient, mock_send: AsyncMock) -> None:
    """AC1: /help returns the help message."""
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_help"])

