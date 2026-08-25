from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from commands.information.models import InformationTopic
from tests.conftest import TEST_SECRET
from translations import get_string

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


def _topic(**overrides) -> InformationTopic:
    defaults = dict(key="mass_times", label_en="Mass Times", body_en="Sundays at 9am.", order=1)
    defaults.update(overrides)
    return InformationTopic(**defaults)  # type: ignore[arg-type]


def _mock_adapter(topics: list[InformationTopic] | None = None) -> MagicMock:
    adapter = MagicMock()
    adapter.list_topics.return_value = topics or []
    return adapter


def test_information_command_sends_one_button_row_per_topic_in_order(
    client: TestClient, mock_send: AsyncMock
) -> None:
    # The adapter contract already guarantees order-sorted output (I-02); this list is
    # given pre-sorted the way a real adapter would return it.
    topics = [_topic(key="b", label_en="Baptism", order=1), _topic(key="a", label_en="Anointing", order=2)]
    app.state.information_adapter = _mock_adapter(topics)
    resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "en")
    assert mock_send.await_args.kwargs["button_rows"] == [
        [("Baptism", "info|topic|b")],
        [("Anointing", "info|topic|a")],
    ]


def test_information_command_shows_intro_with_no_buttons_when_no_topics(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([])
    resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "en")
    assert mock_send.await_args.kwargs["button_rows"] is None


def test_informacion_command_shows_spanish_intro_text(client: TestClient, mock_send: AsyncMock) -> None:
    app.state.information_adapter = _mock_adapter([_topic()])
    resp = client.post("/telegram/webhook", json=_command_update("/información"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "es")


def test_information_command_always_replies_in_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([_topic()])
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "en")


def test_informacion_command_always_replies_in_spanish_even_when_session_language_is_english(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([_topic()])
    with patch("telegram.router.get_language", AsyncMock(return_value="en")):
        resp = client.post("/telegram/webhook", json=_command_update("/información"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "es")
