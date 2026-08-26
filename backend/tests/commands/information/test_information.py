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


def _callback_update(data: str, callback_id: str = "cb1") -> dict:
    return {
        "update_id": 2,
        "callback_query": {
            "id": callback_id,
            "from": {"id": 99, "is_bot": False, "first_name": "Jane"},
            "message": {
                "message_id": 2,
                "chat": {"id": _CHAT_ID, "type": "private"},
                "date": 1_700_000_001,
                "text": "placeholder",
            },
            "data": data,
        },
    }


def _mock_adapter(
    topics: list[InformationTopic] | None = None, get_topic_result: InformationTopic | None = None
) -> MagicMock:
    adapter = MagicMock()
    adapter.list_topics.return_value = topics or []
    adapter.get_topic.return_value = get_topic_result
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


def test_information_command_shows_apology_with_no_buttons_when_no_topics(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([])
    resp = client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_empty", "en")
    assert mock_send.await_args.kwargs["button_rows"] is None


def test_informacion_command_shows_spanish_apology_when_no_topics(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([])
    resp = client.post("/telegram/webhook", json=_command_update("/información"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_empty", "es")


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


# --- Topic selection (I-05) ---------------------------------------------------

def test_tapping_a_topic_shows_its_content_with_a_back_button(
    client: TestClient, mock_send: AsyncMock
) -> None:
    topic = _topic(key="mass_times", body_en="Sundays at 9am.")
    app.state.information_adapter = _mock_adapter(get_topic_result=topic)
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post(
            "/telegram/webhook", json=_callback_update("info|topic|mass_times"), headers=_headers
        )
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == "Sundays at 9am."
    assert mock_send.await_args.kwargs["button_rows"] == [
        [(get_string("information_button_back", "en"), "info|menu")]
    ]


def test_tapping_a_topic_fetches_by_the_key_in_the_callback_data(
    client: TestClient, mock_send: AsyncMock
) -> None:
    adapter = _mock_adapter(get_topic_result=_topic(key="baptism"))
    app.state.information_adapter = adapter
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        client.post("/telegram/webhook", json=_callback_update("info|topic|baptism"), headers=_headers)
    adapter.get_topic.assert_called_once_with("baptism")


def test_tapping_a_removed_topic_sends_nothing(client: TestClient, mock_send: AsyncMock) -> None:
    app.state.information_adapter = _mock_adapter(get_topic_result=None)
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post(
            "/telegram/webhook", json=_callback_update("info|topic|removed"), headers=_headers
        )
    assert resp.status_code == 200
    mock_send.assert_not_awaited()


def test_callback_query_is_answered_before_dispatch(client: TestClient, mock_send: AsyncMock) -> None:
    app.state.information_adapter = _mock_adapter(get_topic_result=_topic())
    with patch("telegram.router.answer_callback_query", AsyncMock()) as answer_mock:
        client.post(
            "/telegram/webhook", json=_callback_update("info|topic|mass_times", "cb-xyz"), headers=_headers
        )
    answer_mock.assert_awaited_once_with("cb-xyz")


def test_tapping_back_to_menu_re_renders_the_menu(client: TestClient, mock_send: AsyncMock) -> None:
    topics = [_topic(key="b", label_en="Baptism", order=1), _topic(key="a", label_en="Anointing", order=2)]
    app.state.information_adapter = _mock_adapter(topics)
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post("/telegram/webhook", json=_callback_update("info|menu"), headers=_headers)
    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_menu_intro", "en")
    assert mock_send.await_args.kwargs["button_rows"] == [
        [("Baptism", "info|topic|b")],
        [("Anointing", "info|topic|a")],
    ]


def test_tapping_back_to_menu_shows_apology_if_the_sheet_became_empty_mid_session(
    client: TestClient, mock_send: AsyncMock
) -> None:
    app.state.information_adapter = _mock_adapter([])
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post("/telegram/webhook", json=_callback_update("info|menu"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("information_empty", "en")
    assert mock_send.await_args.kwargs["button_rows"] is None


def test_tapping_back_to_menu_reflects_admin_edits_made_mid_session(
    client: TestClient, mock_send: AsyncMock
) -> None:
    # The adapter (via its own TTL cache) is re-queried on every tap rather than
    # reusing a stale snapshot held by the presentation layer.
    adapter = _mock_adapter()
    adapter.list_topics.side_effect = [
        [_topic(key="a", label_en="Old Topic", order=1)],
        [_topic(key="a", label_en="Updated Topic", order=1)],
    ]
    app.state.information_adapter = adapter
    with patch("telegram.router.answer_callback_query", AsyncMock()):
        client.post("/telegram/webhook", json=_command_update("/information"), headers=_headers)
        resp = client.post("/telegram/webhook", json=_callback_update("info|menu"), headers=_headers)
    assert resp.status_code == 200
    assert mock_send.await_args is not None
    assert mock_send.await_args.kwargs["button_rows"] == [[("Updated Topic", "info|topic|a")]]


def test_information_callback_is_ignored_when_not_configured(
    client: TestClient, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram.router.information_is_configured", lambda: False)
    app.state.information_adapter = _mock_adapter(get_topic_result=_topic())
    with patch("telegram.router.answer_callback_query", AsyncMock()) as answer_mock:
        resp = client.post(
            "/telegram/webhook", json=_callback_update("info|topic|mass_times"), headers=_headers
        )
    assert resp.status_code == 200
    answer_mock.assert_awaited_once()
    mock_send.assert_not_awaited()
