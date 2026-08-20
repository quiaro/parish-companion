from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from commands.schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType, ScheduleUnavailableError
from tests.conftest import TEST_SECRET

_CHAT_ID = 42

_headers = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}


@pytest.fixture(autouse=True)
def schedules_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /schedules behavior assuming a data source is configured."""
    monkeypatch.setattr("telegram.router.schedules_is_configured", lambda: True)


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


def _mock_adapter(entries: list[ScheduleEntry] | None = None) -> MagicMock:
    adapter = MagicMock()
    adapter.get_schedule.return_value = ParishSchedule(regular=entries or [])
    return adapter


def test_schedules_command_sends_formatted_schedule(client: TestClient, mock_send: AsyncMock) -> None:
    entries = [
        ScheduleEntry(type=ScheduleType.MASS, day="Sunday", start_time="09:00", language=Language.EN),
    ]
    app.state.schedule_adapter = _mock_adapter(entries)
    resp = client.post("/telegram/webhook", json=_command_update("/schedules"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert "Mass Times" in sent_text
    assert "Sunday" in sent_text


def test_horarios_command_always_replies_in_spanish(client: TestClient, mock_send: AsyncMock) -> None:
    app.state.schedule_adapter = _mock_adapter()
    # Session language is English (conftest default), but /horarios forces Spanish.
    resp = client.post("/telegram/webhook", json=_command_update("/horarios"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert "Horarios de Misa" in sent_text


def test_schedules_command_always_replies_in_english(client: TestClient, mock_send: AsyncMock) -> None:
    app.state.schedule_adapter = _mock_adapter()
    # Session language is Spanish, but /schedules forces English.
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/schedules"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert "Mass Times" in sent_text


def test_schedules_command_sends_error_message_when_unavailable(
    client: TestClient, mock_send: AsyncMock
) -> None:
    adapter = MagicMock()
    adapter.get_schedule.side_effect = ScheduleUnavailableError("down")
    app.state.schedule_adapter = adapter
    resp = client.post("/telegram/webhook", json=_command_update("/schedules"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert "/contact" in sent_text
