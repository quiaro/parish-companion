"""Tests for EmailContactNotifier — independent of the Telegram layer."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from commands.contact.email_notifier import EmailContactNotifier
from commands.contact.models import ContactRequest

_REQUEST_EN = ContactRequest(
    name="Jane Smith",
    request_type="General question",
    message="I have a question about RCIA.",
    preferred_time="Weekday evenings",
    telegram_user_id=111222333,
    telegram_username="janesmith",
    language="en",
)

_REQUEST_ES = ContactRequest(
    name="María García",
    request_type="Pregunta general",
    message="Tengo una pregunta sobre el bautismo.",
    preferred_time="Tardes entre semana",
    telegram_user_id=444555666,
    telegram_username=None,
    language="es",
)


def _notifier(monkeypatch: pytest.MonkeyPatch, **overrides) -> EmailContactNotifier:
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
    return EmailContactNotifier()


def _smtp_mock() -> MagicMock:
    """Return a MagicMock that behaves as an SMTP context manager."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    return instance


class TestSendResult:
    def test_returns_true_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch)
        with patch("smtplib.SMTP", return_value=_smtp_mock()):
            assert notifier.send(_REQUEST_EN) is True

    def test_returns_false_when_recipients_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, contact_email_recipients="")
        assert notifier.send(_REQUEST_EN) is False

    def test_returns_false_when_smtp_host_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_host="")
        assert notifier.send(_REQUEST_EN) is False

    def test_returns_false_on_smtp_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch)
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("connection refused")):
            assert notifier.send(_REQUEST_EN) is False

    def test_does_not_raise_on_unexpected_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch)
        with patch("smtplib.SMTP", side_effect=RuntimeError("unexpected")):
            assert notifier.send(_REQUEST_EN) is False


class TestEmailContent:
    def _capture(self, monkeypatch: pytest.MonkeyPatch, request=_REQUEST_EN, **overrides):
        """Send request and return the captured EmailMessage."""
        notifier = _notifier(monkeypatch, **overrides)
        captured = []
        smtp = _smtp_mock()
        smtp.send_message.side_effect = captured.append
        with patch("smtplib.SMTP", return_value=smtp):
            notifier.send(request)
        assert len(captured) == 1
        return captured[0]

    def test_subject_contains_request_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(monkeypatch)
        assert "General question" in msg["Subject"]

    def test_subject_identifies_parish_companion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(monkeypatch)
        assert "Parish Companion" in msg["Subject"]

    def test_body_contains_all_fields_english(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch).get_content()
        assert "Jane Smith" in body
        assert "General question" in body
        assert "I have a question about RCIA." in body
        assert "Weekday evenings" in body
        assert "@janesmith" in body
        assert "111222333" in body

    def test_body_uses_english_labels_for_english_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch).get_content()
        assert "Request type:" in body
        assert "Name:" in body
        assert "Telegram contact:" in body
        assert "Message:" in body
        assert "Best time to reach:" in body

    def test_body_uses_username_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch).get_content()
        assert "@janesmith (ID: 111222333)" in body

    def test_body_uses_id_only_when_username_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch, request=_REQUEST_ES).get_content()
        assert "ID: 444555666" in body
        assert "@" not in body.split("Telegram")[1].split("\n")[0]

    def test_body_uses_spanish_labels_for_spanish_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch, request=_REQUEST_ES).get_content()
        assert "Tipo de solicitud:" in body
        assert "Nombre:" in body
        assert "Contacto de Telegram:" in body
        assert "Mensaje:" in body
        assert "Mejor horario para comunicarse:" in body

    def test_body_contains_all_fields_spanish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = self._capture(monkeypatch, request=_REQUEST_ES).get_content()
        assert "Pregunta general" in body
        assert "María García" in body
        assert "Tardes entre semana" in body
        assert "Tengo una pregunta sobre el bautismo." in body

    def test_to_contains_single_recipient(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(monkeypatch, contact_email_recipients='["staff@parish.org"]')
        assert "staff@parish.org" in msg["To"]

    def test_to_contains_all_recipients_when_multiple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(
            monkeypatch,
            contact_email_recipients='["pastor@parish.org", "secretary@parish.org"]',
        )
        assert "pastor@parish.org" in msg["To"]
        assert "secretary@parish.org" in msg["To"]

    def test_from_uses_smtp_from_address_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(monkeypatch, smtp_from_address="parish@custom.org")
        assert msg["From"] == "parish@custom.org"

    def test_from_falls_back_to_smtp_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        msg = self._capture(monkeypatch, smtp_from_address="", smtp_username="bot@parish.org")
        assert msg["From"] == "bot@parish.org"


class TestSmtpBehavior:
    def test_starttls_called_when_smtp_use_tls_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_use_tls=True)
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            notifier.send(_REQUEST_EN)
        smtp.starttls.assert_called_once()

    def test_starttls_not_called_when_smtp_use_tls_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_use_tls=False)
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            notifier.send(_REQUEST_EN)
        smtp.starttls.assert_not_called()

    def test_login_called_with_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_username="bot@parish.org", smtp_password="secret")
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            notifier.send(_REQUEST_EN)
        smtp.login.assert_called_once_with("bot@parish.org", "secret")

    def test_login_not_called_when_no_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_username="", smtp_use_tls=False)
        smtp = _smtp_mock()
        with patch("smtplib.SMTP", return_value=smtp):
            notifier.send(_REQUEST_EN)
        smtp.login.assert_not_called()

    def test_smtp_called_with_configured_host_and_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notifier = _notifier(monkeypatch, smtp_host="mail.example.com", smtp_port=465)
        with patch("smtplib.SMTP", return_value=_smtp_mock()) as MockSMTP:
            notifier.send(_REQUEST_EN)
        MockSMTP.assert_called_once_with("mail.example.com", 465)
