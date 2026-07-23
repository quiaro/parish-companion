import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from commands.comfort import flow
from commands.comfort.models import ClassificationResult
from commands.comfort.retrieval import RetrievedPassage


@pytest.fixture(autouse=True)
def classify_mock(monkeypatch):
    mock = AsyncMock(return_value=ClassificationResult(is_crisis=False))
    monkeypatch.setattr(flow, "classify", mock)
    return mock


@pytest.fixture(autouse=True)
def retrieve_passage_mock(monkeypatch):
    mock = AsyncMock(
        return_value=RetrievedPassage(reference="Psalm 23:4", verse_text="Test verse text.", is_fallback=False)
    )
    monkeypatch.setattr(flow, "retrieve_passage", mock)
    return mock


@pytest.fixture(autouse=True)
def frame_passage_mock(monkeypatch):
    mock = AsyncMock(return_value="Test framing text.")
    monkeypatch.setattr(flow, "frame_passage", mock)
    return mock


@pytest.fixture
def db_mocks(monkeypatch):
    mocks = {
        "ensure_parishioner": MagicMock(),
        "is_comfort_intro_shown": MagicMock(return_value=False),
        "mark_comfort_intro_shown": MagicMock(),
        "get_last_notification_sent_at": MagicMock(return_value=None),
        "record_notification_sent": MagicMock(),
        "count_recent_passages": MagicMock(return_value=0),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(flow, name, mock)
    return mocks


@pytest.fixture
def crisis_notification_mock(monkeypatch):
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, "send_crisis_notification", mock)
    return mock


@pytest.fixture
def pastoral_outreach_notification_mock(monkeypatch):
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, "send_pastoral_outreach_notification", mock)
    return mock


@pytest.fixture
def flow_store(monkeypatch):
    store: dict[str, dict] = {}

    async def mock_get(sid):
        return copy.deepcopy(store.get(sid))

    async def mock_set(sid, state):
        store[sid] = copy.deepcopy(state)

    async def mock_clear(sid):
        store.pop(sid, None)

    monkeypatch.setattr(flow, "_get_state", mock_get)
    monkeypatch.setattr(flow, "_set_state", mock_set)
    monkeypatch.setattr(flow, "_clear_state", mock_clear)
    return store
