"""Tests for telegram/client.py's outbound Telegram Bot API calls."""

import pytest

import config
from telegram import client


class _FakeResponse:
    def __init__(self, is_success: bool = True):
        self.is_success = is_success
        self.status_code = 200
        self.text = ""


class _FakeAsyncClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse()


@pytest.fixture(autouse=True)
def bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "telegram_bot_token", "test-token")


def _mock_http(monkeypatch: pytest.MonkeyPatch) -> _FakeAsyncClient:
    fake = _FakeAsyncClient()
    monkeypatch.setattr(client.httpx2, "AsyncClient", lambda *a, **k: fake)
    return fake


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_sends_plain_text_without_buttons(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "hello")
        assert len(fake.calls) == 1
        payload = fake.calls[0]["json"]
        assert payload["chat_id"] == 123
        assert payload["text"] == "hello"
        assert "reply_markup" not in payload

    @pytest.mark.asyncio
    async def test_attaches_buttons_as_a_single_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "hello", buttons=[("Yes", "yes_data"), ("No", "no_data")])
        payload = fake.calls[0]["json"]
        assert payload["reply_markup"] == {
            "inline_keyboard": [
                [{"text": "Yes", "callback_data": "yes_data"}, {"text": "No", "callback_data": "no_data"}]
            ]
        }

    @pytest.mark.asyncio
    async def test_buttons_only_attached_to_final_part_of_a_split_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "a" * 400, buttons=[("Yes", "yes_data")])
        assert len(fake.calls) == 2
        assert "reply_markup" not in fake.calls[0]["json"]
        assert "reply_markup" in fake.calls[1]["json"]

    @pytest.mark.asyncio
    async def test_does_nothing_when_bot_token_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config.settings, "telegram_bot_token", "")
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "hello")
        assert fake.calls == []


class TestAnswerCallbackQuery:
    @pytest.mark.asyncio
    async def test_calls_telegram_api_with_callback_query_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.answer_callback_query("cb123")
        assert len(fake.calls) == 1
        assert fake.calls[0]["json"] == {"callback_query_id": "cb123"}

    @pytest.mark.asyncio
    async def test_does_nothing_when_bot_token_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config.settings, "telegram_bot_token", "")
        fake = _mock_http(monkeypatch)
        await client.answer_callback_query("cb123")
        assert fake.calls == []
