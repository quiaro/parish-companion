from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

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


def test_comfort_command_sends_full_intro_on_first_use(client: TestClient, mock_send: AsyncMock) -> None:
    with patch("commands.comfort.flow.ensure_parishioner"), \
         patch("commands.comfort.flow.is_comfort_intro_shown", return_value=False), \
         patch("commands.comfort.flow.mark_comfort_intro_shown") as mark_shown:
        resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
        assert resp.status_code == 200
        mark_shown.assert_called_once_with(_USER_ID)

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_intro", "en")


def test_comfort_command_sends_brief_prompt_on_subsequent_use(client: TestClient, mock_send: AsyncMock) -> None:
    with patch("commands.comfort.flow.ensure_parishioner"), \
         patch("commands.comfort.flow.is_comfort_intro_shown", return_value=True), \
         patch("commands.comfort.flow.mark_comfort_intro_shown") as mark_shown:
        resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
        assert resp.status_code == 200
        mark_shown.assert_not_called()

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_prompt_brief", "en")


def test_comfort_command_always_replies_in_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("commands.comfort.flow.ensure_parishioner"), \
         patch("commands.comfort.flow.is_comfort_intro_shown", return_value=True), \
         patch("commands.comfort.flow.mark_comfort_intro_shown"), \
         patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
        assert resp.status_code == 200

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_prompt_brief", "en")
