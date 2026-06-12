from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from tests.conftest import TEST_SECRET
from translations import STRINGS

_TEXT_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "from": {"id": 99, "first_name": "Alice", "is_bot": False},
        "chat": {"id": 42, "type": "private"},
        "date": 1_700_000_000,
        "text": "hello",
    },
}

_NON_TEXT_UPDATE = {
    "update_id": 2,
    "message": {
        "message_id": 2,
        "chat": {"id": 42, "type": "private"},
        "date": 1_700_000_001,
        # no "text" key — simulates a sticker / voice / file
    },
}

_CHAT_ID = _TEXT_UPDATE["message"]["chat"]["id"]


def test_missing_secret_returns_401(client: TestClient) -> None:
    """AC1: no secret header → 401."""
    resp = client.post("/telegram/webhook", json=_TEXT_UPDATE)
    assert resp.status_code == 401


def test_wrong_secret_returns_401(client: TestClient) -> None:
    """AC1: wrong secret value → 401."""
    resp = client.post(
        "/telegram/webhook",
        json=_TEXT_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 401
    

def test_non_text_message_triggers_text_only_notice(client: TestClient, mock_send: AsyncMock) -> None:
    """AC2: non-text message (sticker/voice/file) returns polite text-only notice."""
    resp = client.post(
        "/telegram/webhook",
        json=_NON_TEXT_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    chat_id, text = mock_send.call_args.args
    assert chat_id == _CHAT_ID
    assert text == STRINGS["en"]["telegram_text_only"]
