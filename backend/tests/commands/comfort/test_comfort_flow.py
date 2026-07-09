"""Tests for the /comfort flow (K-01, K-02, K-04) — independent of the Telegram layer."""

from datetime import datetime, timedelta, timezone

import pytest

import config
from commands.comfort import flow
from translations import get_string

_SESSION = "session_abc"
_UID = 555666777


class TestStart:
    @pytest.mark.asyncio
    async def test_first_use_sends_full_intro(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        reply = await flow.start(_SESSION, _UID, "en")
        assert reply == get_string("comfort_intro", "en")

    @pytest.mark.asyncio
    async def test_first_use_marks_intro_shown(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = False
        await flow.start(_SESSION, _UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_use_calls_ensure_parishioner(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        db_mocks["ensure_parishioner"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_subsequent_use_sends_brief_prompt(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_SESSION, _UID, "en")
        assert reply == get_string("comfort_brief_intro", "en")

    @pytest.mark.asyncio
    async def test_subsequent_use_does_not_remark_intro_shown(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        await flow.start(_SESSION, _UID, "en")
        db_mocks["mark_comfort_intro_shown"].assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_language_argument(self, db_mocks, flow_store) -> None:
        db_mocks["is_comfort_intro_shown"].return_value = True
        reply = await flow.start(_SESSION, _UID, "es")
        assert reply == get_string("comfort_brief_intro", "es")

    @pytest.mark.asyncio
    async def test_stores_flow_state_for_the_session(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        assert flow_store[_SESSION] == {"language": "en", "telegram_user_id": _UID}


class TestHandleText:
    @pytest.mark.asyncio
    async def test_within_limit_returns_placeholder_ack(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_within_limit_clears_flow_state(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "A single word is enough.")
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_exactly_2000_characters_is_accepted(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2000)
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_2001_characters_is_rejected_with_gentle_reprompt(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply == get_string("comfort_input_too_long", "en")

    @pytest.mark.asyncio
    async def test_too_long_submission_keeps_flow_state_for_a_retry(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "a" * 2001)
        assert _SESSION in flow_store

    @pytest.mark.asyncio
    async def test_can_resubmit_after_a_too_long_message(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "a" * 2001)
        reply = await flow.handle_text(_SESSION, "a shorter message")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_length_check_uses_stripped_text(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "  " + "a" * 2000 + "  ")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_respects_stored_session_language(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "es")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply == get_string("comfort_input_too_long", "es")

    @pytest.mark.asyncio
    async def test_no_active_flow_returns_unknown_command_fallback(self, flow_store) -> None:
        reply = await flow.handle_text(_SESSION, "hello")
        assert reply == get_string("telegram_cmd_unknown", "en")

    @pytest.mark.asyncio
    async def test_within_limit_calls_classify_with_stripped_text(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "  I've been feeling anxious lately.  ")
        classify_mock.assert_awaited_once_with("I've been feeling anxious lately.")

    @pytest.mark.asyncio
    async def test_too_long_submission_does_not_call_classify(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "a" * 2001)
        classify_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_failure_still_returns_placeholder_ack(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.side_effect = RuntimeError("OpenRouter is down")
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_classify_failure_still_clears_flow_state(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.side_effect = RuntimeError("OpenRouter is down")
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert _SESSION not in flow_store


class _FrozenDateTime(datetime):
    """Makes datetime.now() inside flow.py deterministic, so the test's notion of "now"
    and the function's notion of "now" are guaranteed to be the same instant — otherwise
    the two separate real now() calls (one in the test, one inside the function a moment
    later) race, and an "exact boundary" case can flip to "just outside" the window."""

    _frozen_now: datetime

    @classmethod
    def now(cls, tz=None):
        return cls._frozen_now


class TestNotificationDedupCheck:
    """
    K-04. Note: test 5 from the story ("neither the crisis notification function nor the
    frequency-nudge notification function is called") is an integration test spanning
    K-05/K-06, which don't exist yet — it belongs in their test suites once built, not here.
    """

    @pytest.fixture
    def frozen_now(self, monkeypatch):
        now = datetime.now(timezone.utc)
        # Dynamically create a subclass of _FrozenDateTime named _Frozen and set its
        # class attribute `_frozen_now` to the current `now`. This makes calls to
        # _Frozen.now() return the deterministic `now` value for testing.
        frozen = type("_Frozen", (_FrozenDateTime,), {"_frozen_now": now})
        monkeypatch.setattr(flow, "datetime", frozen)
        monkeypatch.setattr(config.settings, "comfort_notification_dedup_window_hours", 24)
        return now

    @pytest.mark.asyncio
    async def test_passes_when_never_notified(self, db_mocks) -> None:
        db_mocks["get_last_notification_sent_at"].return_value = None
        assert await flow._notification_dedup_passed(_UID) is True

    @pytest.mark.asyncio
    async def test_fails_exactly_at_window_boundary(self, db_mocks, frozen_now) -> None:
        db_mocks["get_last_notification_sent_at"].return_value = frozen_now - timedelta(hours=24)
        assert await flow._notification_dedup_passed(_UID) is False

    @pytest.mark.asyncio
    async def test_fails_just_inside_window(self, db_mocks, frozen_now) -> None:
        db_mocks["get_last_notification_sent_at"].return_value = (
            frozen_now - timedelta(hours=24) + timedelta(seconds=1)
        )
        assert await flow._notification_dedup_passed(_UID) is False

    @pytest.mark.asyncio
    async def test_passes_just_outside_window(self, db_mocks, frozen_now) -> None:
        db_mocks["get_last_notification_sent_at"].return_value = (
            frozen_now - timedelta(hours=24) - timedelta(seconds=1)
        )
        assert await flow._notification_dedup_passed(_UID) is True
