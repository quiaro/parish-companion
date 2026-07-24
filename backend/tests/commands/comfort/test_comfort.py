from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from commands.comfort.models import ClassificationResult
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


def test_comfort_command_sends_full_intro_on_first_use(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    assert resp.status_code == 200
    db_mocks["mark_comfort_intro_shown"].assert_called_once_with(_USER_ID)

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_intro", "en")


def test_comfort_command_sends_brief_prompt_on_subsequent_use(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    db_mocks["is_comfort_intro_shown"].return_value = True
    resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    assert resp.status_code == 200
    db_mocks["mark_comfort_intro_shown"].assert_not_called()

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_brief_intro", "en")


def test_comfort_command_always_replies_in_english_even_when_session_language_is_spanish(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    db_mocks["is_comfort_intro_shown"].return_value = True
    with patch("telegram.router.get_language", AsyncMock(return_value="es")):
        resp = client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
        assert resp.status_code == 200

    mock_send.assert_awaited_once()
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_brief_intro", "en")


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


def test_free_text_after_comfort_command_returns_verse_reply(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    resp = client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)
    assert resp.status_code == 200

    assert mock_send.await_count == 2
    assert mock_send.await_args is not None
    sent_text = mock_send.await_args[0][1]
    assert sent_text == get_string("comfort_verse_reply", "en").format(
        framing="Test framing text.", reference="Psalm 23:4", verse_text="Test verse text."
    )


def test_overlong_free_text_gets_gentle_reprompt_and_can_be_resubmitted(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("a" * 2001), headers=_headers)
    assert mock_send.await_args is not None
    too_long_reply = mock_send.await_args[0][1]
    assert too_long_reply == get_string("comfort_input_too_long", "en")

    client.post("/telegram/webhook", json=_text_message("a shorter message"), headers=_headers)
    assert mock_send.await_args is not None
    final_reply = mock_send.await_args[0][1]
    assert final_reply == get_string("comfort_verse_reply", "en").format(
        framing="Test framing text.", reference="Psalm 23:4", verse_text="Test verse text."
    )


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


def test_crisis_message_sends_pastoral_message_with_buttons_and_notifies_parish(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store, classify_mock, crisis_notification_mock
) -> None:
    classify_mock.return_value = ClassificationResult(is_crisis=True)
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    resp = client.post(
        "/telegram/webhook", json=_text_message("I don't want to be here anymore."), headers=_headers
    )
    assert resp.status_code == 200

    crisis_notification_mock.assert_awaited_once_with(_USER_ID, "en")
    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("comfort_crisis_message", "en")
    assert mock_send.await_args.kwargs["buttons"] == [
        (get_string("comfort_button_continue", "en"), "comfort_crisis_continue"),
    ]


def test_callback_query_answers_and_dispatches_to_comfort_flow(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store, classify_mock, crisis_notification_mock
) -> None:
    classify_mock.return_value = ClassificationResult(is_crisis=True)
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("I don't want to be here anymore."), headers=_headers)

    with patch("telegram.router.answer_callback_query", AsyncMock()) as answer_mock:
        resp = client.post(
            "/telegram/webhook", json=_callback_update("comfort_crisis_continue"), headers=_headers
        )
        assert resp.status_code == 200
        answer_mock.assert_awaited_once_with("cb1")

    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("comfort_verse_reply", "en").format(
        framing="Test framing text.", reference="Psalm 23:4", verse_text="Test verse text."
    )


def test_verse_reply_records_passage_after_successful_send(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    resp = client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)
    assert resp.status_code == 200

    db_mocks["record_sent_passage"].assert_called_once_with(_USER_ID, "Psalm 23:4")


def test_verse_reply_does_not_record_passage_when_send_fails(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    mock_send.return_value = False
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    resp = client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)
    assert resp.status_code == 200

    db_mocks["record_sent_passage"].assert_not_called()


def test_verse_reply_includes_exit_button(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)

    assert mock_send.await_args is not None
    assert mock_send.await_args.kwargs["buttons"] == [(get_string("comfort_button_exit", "en"), "comfort_exit")]


def test_tapping_exit_replies_like_help_and_does_not_record_again(
    client: TestClient, mock_send: AsyncMock, db_mocks, flow_store
) -> None:
    client.post("/telegram/webhook", json=_command_update("/comfort"), headers=_headers)
    client.post("/telegram/webhook", json=_text_message("I've been feeling anxious lately."), headers=_headers)
    db_mocks["record_sent_passage"].reset_mock()

    with patch("telegram.router.answer_callback_query", AsyncMock()):
        resp = client.post("/telegram/webhook", json=_callback_update("comfort_exit"), headers=_headers)
        assert resp.status_code == 200

    assert mock_send.await_args is not None
    assert mock_send.await_args[0][1] == get_string("telegram_cmd_help", "en")
    db_mocks["record_sent_passage"].assert_not_called()
