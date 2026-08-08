"""
Tests config.py's production-only fail-fast validation.
App notifications depend on SMTP being configured. 
This validator blocks deployment by accident in production, 
but leaves local development/tests unaffected.
"""

import pytest
from pydantic import ValidationError

from config import Settings

_REQUIRED_BASE_KWARGS = {
    "redis_url": "redis://localhost:6379/0",
    "database_url": "postgresql+psycopg://user:pass@localhost:5432/db",
    "local_timezone": "America/Costa_Rica",
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


def test_environment_defaults_to_production() -> None:
    assert Settings.model_fields["environment"].default == "production"
