"""Tests for the /comfort flow's K-01 behavior — independent of the Telegram layer."""

from unittest.mock import MagicMock

import pytest

from commands.comfort import flow
from translations import get_string

_UID = 555666777


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


class TestStart:
    @pytest.mark.asyncio
    async def test_first_use_sends_full_intro(self, db_mocks) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        reply = await flow.start(_UID, "en")
        assert reply == get_string("comfort_intro", "en")

    @pytest.mark.asyncio
    async def test_first_use_marks_intro_shown(self, db_mocks) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        await flow.start(_UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_use_calls_ensure_parishioner(self, db_mocks) -> None:
        await flow.start(_UID, "en")
        db_mocks["ensure_parishioner"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_subsequent_use_sends_brief_prompt(self, db_mocks) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_UID, "en")
        assert reply == get_string("comfort_prompt_brief", "en")

    @pytest.mark.asyncio
    async def test_subsequent_use_does_not_remark_intro_shown(self, db_mocks) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        await flow.start(_UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_language_argument(self, db_mocks) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_UID, "es")
        assert reply == get_string("comfort_prompt_brief", "es")
