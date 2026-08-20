from unittest.mock import AsyncMock, patch

import pytest
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


def _full_help(language: str) -> str:
    return (
        STRINGS[language]["help_intro"]
        + STRINGS[language]["help_line_comfort"]
        + STRINGS[language]["help_line_contact"]
        + STRINGS[language]["help_line_schedules"]
    )


@pytest.fixture(autouse=True)
def all_features_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """By default, exercise /help as if every feature were configured.

    Gating behavior itself is covered separately below.
    """
    monkeypatch.setattr("telegram.commands.comfort_is_configured", lambda: True)
    monkeypatch.setattr("telegram.commands.contact_is_configured", lambda: True)
    monkeypatch.setattr("telegram.commands.schedules_is_configured", lambda: True)


# --- English commands --------------------------------------------------------

def test_start_sends_english_welcome(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/start"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_start"])


def test_help_sends_english_help(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, _full_help("en"))


# --- Spanish commands --------------------------------------------------------

def test_inicio_sends_spanish_welcome(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/inicio"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["es"]["telegram_cmd_start"])


def test_ayuda_sends_spanish_help(client: TestClient, mock_send: AsyncMock) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/ayuda"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, _full_help("es"))


# --- Language is forced regardless of the user's detected language -----------

def test_help_is_always_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, _full_help("en"))


def test_ayuda_is_always_spanish_even_when_session_language_is_english(
    client: TestClient, mock_send: AsyncMock
) -> None:
    with patch("telegram.router.get_language", AsyncMock(return_value="en")):
        resp = client.post("/telegram/webhook", json=_command_update("/ayuda"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, _full_help("es"))


# --- Unconfigured features are hidden from /help and unreachable -------------

def test_help_omits_comfort_line_when_comfort_is_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.commands.comfort_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args.args[1]
    assert "/comfort" not in sent_text
    assert "/contact" in sent_text
    assert "/schedules" in sent_text


def test_help_omits_contact_line_when_contact_is_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.commands.contact_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args.args[1]
    assert "/contact" not in sent_text
    assert "/comfort" in sent_text
    assert "/schedules" in sent_text


def test_comfort_command_is_unreachable_when_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.router.comfort_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_unknown"])


def test_contact_command_is_unreachable_when_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.router.contact_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/contact"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_unknown"])


def test_help_omits_schedules_line_when_schedules_is_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.commands.schedules_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/help"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args.args[1]
    assert "/schedules" not in sent_text
    assert "/comfort" in sent_text
    assert "/contact" in sent_text


def test_schedules_command_is_unreachable_when_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.router.schedules_is_configured", lambda: False)
    resp = client.post("/telegram/webhook", json=_command_update("/schedules"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once_with(_CHAT_ID, STRINGS["en"]["telegram_cmd_unknown"])
