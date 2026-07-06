import copy
from unittest.mock import MagicMock

import pytest

from commands.comfort import flow


@pytest.fixture
def db_mocks(monkeypatch):
    mocks = {
        "ensure_parishioner": MagicMock(),
        "is_comfort_intro_shown": MagicMock(return_value=False),
        "mark_comfort_intro_shown": MagicMock(),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(flow, name, mock)
    return mocks


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
