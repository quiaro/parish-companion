import os

# Set required env vars before config.py is first imported.
# Settings() is instantiated at module level there, so these must be in place
# before any test file imports main or config.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/parish_companion")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("LOCAL_TIMEZONE", "America/Costa_Rica")

from typing import Generator
from unittest.mock import AsyncMock, patch

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
def mock_session_language() -> Generator[None, None, None]:
    """Return no stored language in all tests so default_language is always used."""
    with patch("telegram.router.get_language", AsyncMock(return_value=None)):
        yield


@pytest.fixture(autouse=True)
def pin_default_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin default_language to English so tests are independent of .env locale settings."""
    monkeypatch.setattr(config.settings, "default_language", "en")


@pytest.fixture(autouse=True)
def disable_comfort_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Forces tracing off for every test, regardless of whether env vars
    LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set; otherwise, every test running
    comfort's retrieval.py would create real Langfuse traces.
    """
    from commands.comfort import tracing

    monkeypatch.setattr(tracing, "client", None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def mock_send(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("telegram.router.send_message", mock)
    return mock
