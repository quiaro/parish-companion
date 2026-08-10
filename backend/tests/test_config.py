"""
Tests config.py's fail-fast validation. Email (SMTP/CONTACT_EMAIL_RECIPIENTS) is only
required in production, since app notifications degrade gracefully without it. Telegram
config is required unconditionally, in every environment, since there's no legitimate 
way to run this app at all without a Telegram connection.
"""

import pytest
from pydantic import ValidationError

from config import Settings

_REQUIRED_BASE_KWARGS = {
    "redis_url": "redis://localhost:6379/0",
    "database_url": "postgresql+psycopg://user:pass@localhost:5432/db",
    "local_timezone": "America/Costa_Rica",
    # Valid defaults for every other required field, so each test class below can
    # override only the field(s) it's actually testing without tripping a different
    # validator first.
    "telegram_bot_token": "test-token",
    "telegram_webhook_url": "https://example.com/webhook",
    "telegram_webhook_secret": "test-secret",
    "smtp_host": "smtp.parish.org",
    "contact_email_recipients": '["pastor@parish.org"]',
}


def _settings(**overrides) -> Settings:
    return Settings(**{**_REQUIRED_BASE_KWARGS, **overrides})  # type: ignore[call-arg]


class TestProductionEmailValidation:
    def test_raises_when_smtp_host_missing(self) -> None:
        with pytest.raises(ValidationError, match="SMTP_HOST"):
            _settings(
                environment="production",
                smtp_host="",
                contact_email_recipients='["pastor@parish.org"]',
            )

    def test_raises_when_contact_email_recipients_missing(self) -> None:
        with pytest.raises(ValidationError, match="CONTACT_EMAIL_RECIPIENTS"):
            _settings(environment="production", smtp_host="smtp.parish.org", contact_email_recipients="")

    def test_raises_when_contact_email_recipients_is_empty_json_array(self) -> None:
        with pytest.raises(ValidationError, match="CONTACT_EMAIL_RECIPIENTS"):
            _settings(environment="production", smtp_host="smtp.parish.org", contact_email_recipients="[]")

    def test_raises_when_contact_email_recipients_is_not_json(self) -> None:
        with pytest.raises(ValidationError, match="CONTACT_EMAIL_RECIPIENTS"):
            _settings(
                environment="production", smtp_host="smtp.parish.org", contact_email_recipients="not json"
            )

    def test_raises_when_both_missing_and_names_both(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _settings(environment="production", smtp_host="", contact_email_recipients="")
        message = str(exc_info.value)
        assert "SMTP_HOST" in message
        assert "CONTACT_EMAIL_RECIPIENTS" in message

    def test_does_not_raise_when_both_configured(self) -> None:
        settings = _settings(
            environment="production",
            smtp_host="smtp.parish.org",
            contact_email_recipients='["pastor@parish.org"]',
        )
        assert settings.smtp_host == "smtp.parish.org"
        assert settings.contact_email_recipients == '["pastor@parish.org"]'

    def test_does_not_raise_in_development_when_unconfigured(self) -> None:
        settings = _settings(environment="development", smtp_host="", contact_email_recipients="")
        assert settings.smtp_host == ""


class TestTelegramValidation:
    """Unlike email, this is required in every environment; see `must_have_telegram_configured`
    in config.py."""

    def test_raises_when_bot_token_missing(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_BOT_TOKEN"):
            _settings(telegram_bot_token="")

    def test_raises_when_webhook_url_missing(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_WEBHOOK_URL"):
            _settings(telegram_webhook_url="")

    def test_raises_when_webhook_secret_missing(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_WEBHOOK_SECRET"):
            _settings(telegram_webhook_secret="")

    def test_raises_when_all_missing_and_names_all(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _settings(telegram_bot_token="", telegram_webhook_url="", telegram_webhook_secret="")
        message = str(exc_info.value)
        assert "TELEGRAM_BOT_TOKEN" in message
        assert "TELEGRAM_WEBHOOK_URL" in message
        assert "TELEGRAM_WEBHOOK_SECRET" in message

    def test_does_not_raise_when_all_configured(self) -> None:
        settings = _settings()
        assert settings.telegram_bot_token == "test-token"
        assert settings.telegram_webhook_url == "https://example.com/webhook"
        assert settings.telegram_webhook_secret == "test-secret"

    def test_raises_even_in_development_when_unconfigured(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_BOT_TOKEN"):
            _settings(environment="development", telegram_bot_token="")


def test_environment_defaults_to_production() -> None:
    assert Settings.model_fields["environment"].default == "production"
