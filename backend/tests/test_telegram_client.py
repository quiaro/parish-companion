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
    def __init__(self, response: "_FakeResponse | None" = None, raise_error: Exception | None = None):
        self.calls: list[dict] = []
        self._response = response or _FakeResponse()
        self._raise_error = raise_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self._raise_error:
            raise self._raise_error
        return self._response

    async def get(self, url, timeout=None):
        self.calls.append({"url": url, "timeout": timeout})
        if self._raise_error:
            raise self._raise_error
        return self._response


@pytest.fixture(autouse=True)
def bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "telegram_bot_token", "test-token")


def _mock_http(
    monkeypatch: pytest.MonkeyPatch,
    response: "_FakeResponse | None" = None,
    raise_error: Exception | None = None,
) -> _FakeAsyncClient:
    fake = _FakeAsyncClient(response=response, raise_error=raise_error)
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
    async def test_attaches_button_rows_as_separate_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(
            123, "hello", button_rows=[[("A", "a_data")], [("B", "b_data")]]
        )
        payload = fake.calls[0]["json"]
        assert payload["reply_markup"] == {
            "inline_keyboard": [
                [{"text": "A", "callback_data": "a_data"}],
                [{"text": "B", "callback_data": "b_data"}],
            ]
        }

    @pytest.mark.asyncio
    async def test_button_rows_only_attached_to_final_part_of_a_split_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "a" * 400, button_rows=[[("A", "a_data")]])
        assert len(fake.calls) == 2
        assert "reply_markup" not in fake.calls[0]["json"]
        assert "reply_markup" in fake.calls[1]["json"]

    @pytest.mark.asyncio
    async def test_empty_button_rows_list_omits_reply_markup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.send_message(123, "hello", button_rows=None)
        payload = fake.calls[0]["json"]
        assert "reply_markup" not in payload

    @pytest.mark.asyncio
    async def test_logs_and_returns_false_when_telegram_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.ConnectTimeout("timed out"))
        with caplog.at_level("ERROR"):
            result = await client.send_message(123, "hello")
        assert result is False
        assert any("network problem reaching Telegram" in message for message in caplog.messages)


class TestAnswerCallbackQuery:
    @pytest.mark.asyncio
    async def test_calls_telegram_api_with_callback_query_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.answer_callback_query("cb123")
        assert len(fake.calls) == 1
        assert fake.calls[0]["json"] == {"callback_query_id": "cb123"}

    @pytest.mark.asyncio
    async def test_logs_and_does_not_raise_when_telegram_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.ConnectTimeout("timed out"))
        with caplog.at_level("ERROR"):
            await client.answer_callback_query("cb123")
        assert any("network problem reaching Telegram" in message for message in caplog.messages)


class TestCheckConnectivity:
    @pytest.mark.asyncio
    async def test_returns_true_when_telegram_is_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_http(monkeypatch)
        assert await client.check_connectivity() is True

    @pytest.mark.asyncio
    async def test_returns_false_and_logs_when_telegram_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.ConnectTimeout("timed out"))
        with caplog.at_level("ERROR"):
            result = await client.check_connectivity()
        assert result is False
        assert any("network problem reaching Telegram" in message for message in caplog.messages)


@pytest.fixture(autouse=True)
def webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "telegram_webhook_url", "https://example.com/webhook")


class TestRegisterWebhook:
    @pytest.mark.asyncio
    async def test_registers_with_configured_url_and_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config.settings, "telegram_webhook_secret", "shh")
        fake = _mock_http(monkeypatch)
        await client.register_webhook()
        assert len(fake.calls) == 1
        assert fake.calls[0]["json"] == {"url": "https://example.com/webhook", "secret_token": "shh"}

    @pytest.mark.asyncio
    async def test_logs_and_raises_when_telegram_rejects_the_request(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, response=_FakeResponse(is_success=False))
        with caplog.at_level("ERROR"), pytest.raises(RuntimeError, match="setWebhook failed"):
            await client.register_webhook()
        assert any("setWebhook failed" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_logs_a_generic_message_when_the_request_error_is_not_a_transport_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.RequestError("connection failed"))
        with caplog.at_level("ERROR"), pytest.raises(client.httpx2.RequestError):
            await client.register_webhook()
        assert any("Could not reach Telegram to register webhook" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_logs_a_network_hint_when_the_failure_is_a_connection_timeout(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.ConnectTimeout("timed out"))
        with caplog.at_level("ERROR"), pytest.raises(client.httpx2.ConnectTimeout):
            await client.register_webhook()
        assert any("network problem reaching Telegram" in message for message in caplog.messages)


class TestDeleteWebhook:
    @pytest.mark.asyncio
    async def test_deletes_with_configured_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _mock_http(monkeypatch)
        await client.delete_webhook()
        assert len(fake.calls) == 1

    @pytest.mark.asyncio
    async def test_logs_and_does_not_raise_when_telegram_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _mock_http(monkeypatch, raise_error=client.httpx2.RequestError("connection failed"))
        with caplog.at_level("ERROR"):
            await client.delete_webhook()
        assert any("Could not reach Telegram to delete webhook" in message for message in caplog.messages)
