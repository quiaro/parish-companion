from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_SECRET
from translations import STRINGS

_CHAT_ID = 42

_headers = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}


@pytest.fixture(autouse=True)
def information_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /information behavior assuming a data source is configured."""
    monkeypatch.setattr("telegram.router.information_is_configured", lambda: True)


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


def test_information_command_sends_english_placeholder(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["information_ack_placeholder"])


def test_informacion_command_sends_spanish_placeholder(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/información"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["information_ack_placeholder"])


def test_information_command_always_replies_in_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["information_ack_placeholder"])


def test_informacion_command_always_replies_in_spanish_even_when_session_language_is_english(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="en")):
        resp = client.post("/telegram/webhook", json=_command_update("/información"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["information_ack_placeholder"])
