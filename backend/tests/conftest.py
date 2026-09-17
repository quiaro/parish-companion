import os

# Set required env vars before config.py is first imported.
# Settings() is instantiated at module level there, so these must be in place
# before any test file imports main or config.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/parish_companion")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_WEBHOOK_URL", "https://example.com/webhook")
os.environ.setdefault("LOCAL_TIMEZONE", "America/Costa_Rica")

# The only reliable way to guarantee the test suite never creates real traces is to ensure
# tracing is never enabled in the first place, before config.py is ever imported.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

os.environ["ENVIRONMENT"] = "development"

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import config
from main import app

TEST_SECRET = "test-secret"


@pytest.fixture(autouse=True)
def enforce_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the webhook secret to a known value for every test."""
    monkeypatch.setattr(config.settings, "telegram_webhook_secret", TEST_SECRET)


@pytest.fixture(autouse=True)
def pin_default_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin default_language to English so tests are independent of .env locale settings."""
    monkeypatch.setattr(config.settings, "default_language", "en")


@pytest.fixture(autouse=True)
def pin_supported_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin supported_languages to both so tests are independent of .env locale settings."""
    monkeypatch.setattr(config.settings, "supported_languages", '["en", "es"]')


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def mock_send(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("telegram.router.send_message", mock)
    return mock
