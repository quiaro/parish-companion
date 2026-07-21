"""Tests for send_crisis_notification — independent of the Telegram layer."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from commands.comfort.notifications import send_crisis_notification

_UID = 111222333


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    import config

    defaults = dict(
        contact_email_recipients='["staff@parish.org"]',
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="bot@parish.org",
        smtp_password="secret",
        smtp_use_tls=True,
        smtp_from_address="",
    )
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(config.settings, key, value)


def _smtp_mock() -> MagicMock:
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    return instance


class TestSendResult:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch)
        with patch("smtplib.SMTP", return_value=_smtp_mock()):
            assert await send_crisis_notification(_UID) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_recipients_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch, contact_email_recipients="")
        assert await send_crisis_notification(_UID) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_smtp_host_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch, smtp_host="")
        assert await send_crisis_notification(_UID) is False

    @pytest.mark.asyncio
    async def test_returns_false_on_smtp_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch)
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("connection refused")):
            assert await send_crisis_notification(_UID) is False

    @pytest.mark.asyncio
    async def test_does_not_raise_on_unexpected_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch)
        with patch("smtplib.SMTP", side_effect=RuntimeError("unexpected")):
            assert await send_crisis_notification(_UID) is False


class TestEmailContent:
    async def _capture(self, monkeypatch: pytest.MonkeyPatch, language: str = "en", **overrides):
        _configure(monkeypatch, **overrides)
        captured = []
        smtp = _smtp_mock()
        smtp.send_message.side_effect = captured.append
        with patch("smtplib.SMTP", return_value=smtp):
            await send_crisis_notification(_UID, language)
        assert len(captured) == 1
        return captured[0]

    @pytest.mark.asyncio
    async def test_subject_identifies_urgent_crisis_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = await self._capture(monkeypatch)
        assert "Urgent" in msg["Subject"]
        assert "/comfort" in msg["Subject"]

    @pytest.mark.asyncio
    async def test_body_contains_telegram_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (await self._capture(monkeypatch)).get_content()
        assert str(_UID) in body

    @pytest.mark.asyncio
    async def test_subject_and_body_are_localized_to_spanish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = await self._capture(monkeypatch, language="es")
        assert "Urgente" in msg["Subject"]
        assert "/consolar" in msg["Subject"]
        body = msg.get_content()
        assert "feligrés" in body
        assert str(_UID) in body

    @pytest.mark.asyncio
    async def test_defaults_to_english_when_language_not_passed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch)
        captured = []
        smtp = _smtp_mock()
        smtp.send_message.side_effect = captured.append
        with patch("smtplib.SMTP", return_value=smtp):
            await send_crisis_notification(_UID)
        assert "Urgent" in captured[0]["Subject"]

    @pytest.mark.asyncio
    async def test_to_contains_all_recipients(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = await self._capture(
            monkeypatch, contact_email_recipients='["pastor@parish.org", "secretary@parish.org"]'
        )
        assert "pastor@parish.org" in msg["To"]
        assert "secretary@parish.org" in msg["To"]

    @pytest.mark.asyncio
    async def test_from_uses_smtp_from_address_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = await self._capture(monkeypatch, smtp_from_address="parish@custom.org")
        assert msg["From"] == "parish@custom.org"

    @pytest.mark.asyncio
    async def test_from_falls_back_to_smtp_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = await self._capture(monkeypatch, smtp_from_address="", smtp_username="bot@parish.org")
        assert msg["From"] == "bot@parish.org"


class TestSmtpBehavior:
    @pytest.mark.asyncio
    async def test_starttls_called_when_smtp_use_tls_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch, smtp_use_tls=True)
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            await send_crisis_notification(_UID)
        smtp.starttls.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_called_with_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch, smtp_username="bot@parish.org", smtp_password="secret")
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            await send_crisis_notification(_UID)
        smtp.login.assert_called_once_with("bot@parish.org", "secret")

    @pytest.mark.asyncio
    async def test_smtp_called_with_configured_host_and_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _configure(monkeypatch, smtp_host="mail.example.com", smtp_port=465)
        with patch("smtplib.SMTP", return_value=_smtp_mock()) as MockSMTP:
            await send_crisis_notification(_UID)
        MockSMTP.assert_called_once_with("mail.example.com", 465)
