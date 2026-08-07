"""Tests for the /comfort flow — independent of the Telegram layer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import ANY

import pytest

import config
from commands.comfort import flow
from commands.comfort.models import ClassificationResult, EmotionalTag, SituationalTag
from commands.comfort.retrieval import RetrievedPassage
from translations import get_string

_SESSION = "session_abc"
_UID = 555666777


def _expected_verse_reply(language: str = "en") -> str:
    """Matches the fixed RetrievedPassage/framing text returned by the autouse
    retrieve_passage_mock/frame_passage_mock fixtures in conftest.py."""
    return get_string("comfort_verse_reply", language).format(
        framing="Test framing text.", reference="Psalm 23:4", verse_text="Test verse text."
    )


def _navigation_buttons(language: str = "en") -> list[tuple[str, str]]:
    return [
        (get_string("comfort_button_view_another", language), "comfort_view_another"),
        (get_string("comfort_button_exit", language), "comfort_exit"),
    ]


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
        assert flow_store[_SESSION] == {
            "language": "en",
            "telegram_user_id": _UID,
            "step": "awaiting_text",
        }


class TestHandleText:
    @pytest.mark.asyncio
    async def test_within_limit_returns_verse_reply(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_within_limit_returns_navigation_buttons(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply is not None
        assert reply.buttons == _navigation_buttons()

    @pytest.mark.asyncio
    async def test_within_limit_flags_record_passage_on_success(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert reply is not None
        assert reply.record_passage_on_success is True

    @pytest.mark.asyncio
    async def test_within_limit_sets_awaiting_navigation_state(self, db_mocks, flow_store) -> None:
        # State is kept alive to record the passage post-send, and to support both
        # View another passage and Exit.
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "A single word is enough.")
        assert flow_store[_SESSION]["step"] == "awaiting_navigation"
        assert flow_store[_SESSION]["passage_reference"] == "Psalm 23:4"
        assert flow_store[_SESSION]["raw_text"] == "A single word is enough."
        assert flow_store[_SESSION]["classification"] == {
            "is_crisis": False,
            "emotional_tags": [],
            "situational_tags": [],
        }

    @pytest.mark.asyncio
    async def test_exactly_2000_characters_is_accepted(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2000)
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_2001_characters_is_rejected_with_gentle_reprompt(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply is not None
        assert reply.text == get_string("comfort_input_too_long", "en")

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
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_length_check_uses_stripped_text(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "  " + "a" * 2000 + "  ")
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_respects_stored_session_language(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "es")
        reply = await flow.handle_text(_SESSION, "a" * 2001)
        assert reply is not None
        assert reply.text == get_string("comfort_input_too_long", "es")

    @pytest.mark.asyncio
    async def test_no_active_flow_returns_unknown_command_fallback(self, flow_store) -> None:
        reply = await flow.handle_text(_SESSION, "hello")
        assert reply is not None
        assert reply.text == get_string("telegram_cmd_unknown", "en")

    @pytest.mark.asyncio
    async def test_within_limit_calls_classify_with_stripped_text(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "  I've been feeling anxious lately.  ")
        classify_mock.assert_awaited_once_with("I've been feeling anxious lately.", ANY)

    @pytest.mark.asyncio
    async def test_calls_retrieve_passage_with_stripped_text_and_classification(
        self, db_mocks, flow_store, classify_mock, retrieve_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.HOPE])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "  I've been feeling anxious lately.  ")
        retrieve_passage_mock.assert_awaited_once_with(
            _UID, "I've been feeling anxious lately.", classify_mock.return_value, ANY, "en"
        )

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
        assert reply is not None
        assert reply.text == get_string("comfort_ack_placeholder", "en")

    @pytest.mark.asyncio
    async def test_classify_failure_still_clears_flow_state(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.side_effect = RuntimeError("OpenRouter is down")
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_stray_text_ignored_while_awaiting_a_button_tap(
        self, db_mocks, flow_store
    ) -> None:
        await flow._set_state(
            _SESSION, {"language": "en", "telegram_user_id": _UID, "step": "awaiting_crisis_response"}
        )
        reply = await flow.handle_text(_SESSION, "some stray message")
        assert reply is None


class TestAggregateStatRecording:
    """Anonymized /comfort usage stats recorded once per successful classification."""

    @pytest.mark.asyncio
    async def test_recorded_after_successful_classification(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(
            is_crisis=False, emotional_tags=[EmotionalTag.JOY], situational_tags=[SituationalTag.NEW_JOB]
        )
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "Today was a good day.")

        db_mocks["record_comfort_aggregate_stat"].assert_called_once_with(False, ["joy"], ["new_job"])

    @pytest.mark.asyncio
    async def test_recorded_even_when_crisis_flagged(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True, emotional_tags=[EmotionalTag.DESPAIR])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        db_mocks["record_comfort_aggregate_stat"].assert_called_once_with(True, ["despair"], [])

    @pytest.mark.asyncio
    async def test_not_recorded_when_classify_fails(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.side_effect = RuntimeError("Classification LLM is down")
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        db_mocks["record_comfort_aggregate_stat"].assert_not_called()

    @pytest.mark.asyncio
    async def test_not_recorded_again_on_view_another_passage(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        # "View another passage" reuses the stored classification rather than
        # reclassifying, so no new classification event exists to record.
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        db_mocks["record_comfort_aggregate_stat"].reset_mock()

        await flow.handle_callback(_SESSION, "comfort_view_another")

        db_mocks["record_comfort_aggregate_stat"].assert_not_called()

    @pytest.mark.asyncio
    async def test_recording_failure_does_not_block_the_reply(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        db_mocks["record_comfort_aggregate_stat"].side_effect = RuntimeError("Postgres is down")
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        assert reply is not None
        assert reply.text == _expected_verse_reply()


class TestCrisisGate:
    @pytest.mark.asyncio
    async def test_crisis_message_triggers_notification_and_updates_timestamp(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True, emotional_tags=[EmotionalTag.DESPAIR])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        crisis_notification_mock.assert_awaited_once_with(_UID, "en")
        db_mocks["record_notification_sent"].assert_called_once_with(_UID)

    @pytest.mark.asyncio
    async def test_failed_notification_does_not_update_timestamp(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        crisis_notification_mock.return_value = False
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        db_mocks["record_notification_sent"].assert_not_called()

    @pytest.mark.asyncio
    async def test_crisis_message_returns_pastoral_message_with_buttons(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        assert reply is not None
        assert reply.text == get_string("comfort_crisis_message", "en")
        assert reply.buttons == [(get_string("comfort_button_continue", "en"), "comfort_crisis_continue")]

    @pytest.mark.asyncio
    async def test_retrieval_never_called_before_continue_is_tapped(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock, retrieve_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(
            is_crisis=True, emotional_tags=[EmotionalTag.JOY], situational_tags=[SituationalTag.NEW_JOB]
        )
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        retrieve_passage_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_crisis_message_stores_classification_and_awaits_response(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True, emotional_tags=[EmotionalTag.DESPAIR])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        assert flow_store[_SESSION]["step"] == "awaiting_crisis_response"
        assert flow_store[_SESSION]["raw_text"] == "I don't want to be here anymore."
        assert flow_store[_SESSION]["classification"] == {
            "is_crisis": True,
            "emotional_tags": ["despair"],
            "situational_tags": [],
        }

    @pytest.mark.asyncio
    async def test_non_crisis_message_does_not_notify(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False)
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "Today was a good day.")

        crisis_notification_mock.assert_not_called()
        db_mocks["record_notification_sent"].assert_not_called()
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_crisis_gate_skipped_when_dedup_check_fails(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        db_mocks["get_last_notification_sent_at"].return_value = datetime.now(timezone.utc)
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        crisis_notification_mock.assert_not_called()
        db_mocks["record_notification_sent"].assert_not_called()
        assert reply is not None
        assert reply.text == _expected_verse_reply()


class TestEscalationGate:
    @pytest.mark.asyncio
    async def test_threshold_count_does_not_escalate(self, db_mocks, flow_store, classify_mock) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 10
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I keep asking for verses.")

        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_above_threshold_with_high_risk_tag_escalates(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(
            is_crisis=False, emotional_tags=[EmotionalTag.HOPELESSNESS, EmotionalTag.EXHAUSTION]
        )
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I keep asking for verses.")

        assert reply is not None
        assert reply.text == get_string("comfort_escalation_message", "en")
        assert reply.buttons == [
            (get_string("comfort_button_yes", "en"), "comfort_escalation_yes"),
            (get_string("comfort_button_no", "en"), "comfort_escalation_no"),
        ]

    @pytest.mark.asyncio
    async def test_above_threshold_without_high_risk_tag_does_not_escalate(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.EXHAUSTION])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I keep asking for verses.")

        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_uses_configured_frequency_window(
        self, db_mocks, flow_store, classify_mock, monkeypatch
    ) -> None:
        monkeypatch.setattr(config.settings, "comfort_frequency_window_hours", 12)
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.RAGE])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        db_mocks["count_recent_passages"].assert_called_once_with(_UID, 12)

    @pytest.mark.asyncio
    async def test_escalation_stores_classification_and_awaits_response(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.LONELINESS])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        assert flow_store[_SESSION]["step"] == "awaiting_escalation_response"
        assert flow_store[_SESSION]["raw_text"] == "I keep asking for verses."
        assert flow_store[_SESSION]["classification"] == {
            "is_crisis": False,
            "emotional_tags": ["loneliness"],
            "situational_tags": [],
        }

    @pytest.mark.asyncio
    async def test_skipped_entirely_when_is_crisis_true(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        db_mocks["count_recent_passages"].assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_entirely_when_dedup_check_fails(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["get_last_notification_sent_at"].return_value = datetime.now(timezone.utc)
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        db_mocks["count_recent_passages"].assert_not_called()
        pastoral_outreach_notification_mock.assert_not_called()


class TestHandleCallback:
    @pytest.mark.asyncio
    async def test_continue_returns_verse_reply_without_reclassifying(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock, retrieve_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")
        classify_mock.reset_mock()

        reply = await flow.handle_callback(_SESSION, "comfort_crisis_continue")

        assert reply is not None
        assert reply.text == _expected_verse_reply()
        classify_mock.assert_not_called()
        retrieve_passage_mock.assert_awaited_once_with(
            _UID, "I don't want to be here anymore.", ClassificationResult(is_crisis=True), ANY, "en"
        )

    @pytest.mark.asyncio
    async def test_continue_sets_awaiting_navigation_state(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        await flow.handle_callback(_SESSION, "comfort_crisis_continue")

        assert flow_store[_SESSION]["step"] == "awaiting_navigation"

    @pytest.mark.asyncio
    async def test_escalation_yes_sends_notification_and_updates_timestamp(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        reply = await flow.handle_callback(_SESSION, "comfort_escalation_yes")

        pastoral_outreach_notification_mock.assert_awaited_once_with(_UID, "en")
        db_mocks["record_notification_sent"].assert_called_once_with(_UID)
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_escalation_yes_sets_awaiting_navigation_state(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        await flow.handle_callback(_SESSION, "comfort_escalation_yes")

        assert flow_store[_SESSION]["step"] == "awaiting_navigation"

    @pytest.mark.asyncio
    async def test_escalation_yes_failed_notification_does_not_update_timestamp(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        pastoral_outreach_notification_mock.return_value = False
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        await flow.handle_callback(_SESSION, "comfort_escalation_yes")

        db_mocks["record_notification_sent"].assert_not_called()

    @pytest.mark.asyncio
    async def test_escalation_no_sends_no_notification(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        reply = await flow.handle_callback(_SESSION, "comfort_escalation_no")

        pastoral_outreach_notification_mock.assert_not_called()
        db_mocks["record_notification_sent"].assert_not_called()
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_escalation_no_sets_awaiting_navigation_state(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        await flow.handle_callback(_SESSION, "comfort_escalation_no")

        assert flow_store[_SESSION]["step"] == "awaiting_navigation"

    @pytest.mark.asyncio
    async def test_no_pending_state_returns_none(self, flow_store) -> None:
        reply = await flow.handle_callback(_SESSION, "comfort_crisis_continue")
        assert reply is None

    @pytest.mark.asyncio
    async def test_wrong_step_returns_none(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")  # step == "awaiting_text"
        reply = await flow.handle_callback(_SESSION, "comfort_crisis_continue")
        assert reply is None

    @pytest.mark.asyncio
    async def test_unrecognized_callback_data_returns_none(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        reply = await flow.handle_callback(_SESSION, "not_a_real_action")
        assert reply is None

    @pytest.mark.asyncio
    async def test_escalation_data_ignored_while_in_crisis_step(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")

        reply = await flow.handle_callback(_SESSION, "comfort_escalation_yes")
        assert reply is None

    @pytest.mark.asyncio
    async def test_crisis_data_ignored_while_in_escalation_step(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")

        reply = await flow.handle_callback(_SESSION, "comfort_crisis_continue")
        assert reply is None


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


class TestFraming:
    """K-08: framing is skipped entirely on the Step G fallback path, and a framing
    failure gracefully degrades to the bare verse rather than blocking the reply."""

    @pytest.mark.asyncio
    async def test_real_match_includes_framing(
        self, db_mocks, flow_store, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        frame_passage_mock.assert_awaited_once()
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_fallback_passage_skips_framing(
        self, db_mocks, flow_store, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        retrieve_passage_mock.return_value = RetrievedPassage(
            reference="Joel 2:25", verse_text="Fallback verse text.", verse_text_es="Texto de respaldo.", is_fallback=True
        )
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "gibberish unrelated to anything")

        frame_passage_mock.assert_not_called()
        assert reply is not None
        assert reply.text == get_string("comfort_fallback_message", "en").format(
            reference="Joel 2:25", verse_text="Fallback verse text."
        )

    @pytest.mark.asyncio
    async def test_framing_failure_falls_back_to_bare_verse(
        self, db_mocks, flow_store, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        frame_passage_mock.side_effect = RuntimeError("LLM provider is down")
        await flow.start(_SESSION, _UID, "en")
        reply = await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        assert reply is not None
        assert reply.text == get_string("comfort_verse_reply_no_framing", "en").format(
            reference="Psalm 23:4", verse_text="Test verse text."
        )


class TestLangfuseSessionGrouping:
    """A fresh, random langfuse_session_id is minted once per free-text submission
    (see flow.handle_text) and threaded through classify/retrieve_passage/frame_passage
    so a single parishioner request's Langfuse traces group together, without linking
    separate requests to each other."""

    @pytest.mark.asyncio
    async def test_classify_retrieve_and_frame_share_the_same_session_id(
        self, db_mocks, flow_store, classify_mock, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.HOPE])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        classify_session_id = classify_mock.call_args.args[1]
        retrieve_session_id = retrieve_passage_mock.call_args.args[3]
        frame_session_id = frame_passage_mock.call_args.args[3]
        assert classify_session_id == retrieve_session_id == frame_session_id

    @pytest.mark.asyncio
    async def test_crisis_continue_reuses_the_session_id_from_classification(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock, retrieve_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")
        classify_session_id = classify_mock.call_args.args[1]

        await flow.handle_callback(_SESSION, "comfort_crisis_continue")

        retrieve_session_id = retrieve_passage_mock.call_args.args[3]
        assert retrieve_session_id == classify_session_id

    @pytest.mark.asyncio
    async def test_view_another_reuses_the_session_id_from_the_original_request(
        self, db_mocks, flow_store, classify_mock, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.HOPE])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        first_session_id = retrieve_passage_mock.call_args.args[3]
        retrieve_passage_mock.reset_mock()

        await flow.handle_callback(_SESSION, "comfort_view_another")

        second_session_id = retrieve_passage_mock.call_args.args[3]
        assert second_session_id == first_session_id

    @pytest.mark.asyncio
    async def test_two_separate_submissions_get_different_session_ids(
        self, db_mocks, flow_store, classify_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        first_session_id = classify_mock.call_args.args[1]
        classify_mock.reset_mock()

        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "A completely different message.")
        second_session_id = classify_mock.call_args.args[1]

        assert first_session_id != second_session_id


class TestExit:
    """K-09 (Exit button): tapping Exit ends the flow like /help; free text while
    awaiting the tap is silently ignored, same as any other pending-button step."""

    @pytest.mark.asyncio
    async def test_tapping_exit_returns_help_reply(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        reply = await flow.handle_callback(_SESSION, "comfort_exit")

        assert reply is not None
        assert reply.text == get_string("telegram_cmd_help", "en")
        assert reply.buttons is None

    @pytest.mark.asyncio
    async def test_tapping_exit_returns_help_reply_in_spanish_session(self, db_mocks, flow_store) -> None:
        # Exit must respect the session's language, not hardcode English.
        await flow.start(_SESSION, _UID, "es")
        await flow.handle_text(_SESSION, "Me he sentido ansioso últimamente.")

        reply = await flow.handle_callback(_SESSION, "comfort_exit")

        assert reply is not None
        assert reply.text == get_string("telegram_cmd_help", "es")

    @pytest.mark.asyncio
    async def test_tapping_exit_clears_flow_state(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        await flow.handle_callback(_SESSION, "comfort_exit")

        assert _SESSION not in flow_store

    @pytest.mark.asyncio
    async def test_stray_text_ignored_while_awaiting_navigation(
        self, db_mocks, flow_store, retrieve_passage_mock, frame_passage_mock
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        reply = await flow.handle_text(_SESSION, "some stray message")

        assert reply is None
        assert flow_store[_SESSION]["step"] == "awaiting_navigation"
        retrieve_passage_mock.assert_awaited_once()
        frame_passage_mock.assert_awaited_once()


class TestViewAnotherPassage:
    """K-09 (View another passage button): restarts straight at Step F/G/H, reusing the
    stored raw_text/classification — no reclassification, and no re-entry into Step
    C/D/E since the parishioner already passed through gating once for this message."""

    @pytest.mark.asyncio
    async def test_calls_retrieve_passage_with_stored_raw_text_and_classification(
        self, db_mocks, flow_store, classify_mock, retrieve_passage_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.HOPE])
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        retrieve_passage_mock.reset_mock()
        classify_mock.reset_mock()

        reply = await flow.handle_callback(_SESSION, "comfort_view_another")

        assert reply is not None
        classify_mock.assert_not_called()
        retrieve_passage_mock.assert_awaited_once_with(
            _UID, "I've been feeling anxious lately.", ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.HOPE]), ANY, "en"
        )

    @pytest.mark.asyncio
    async def test_skips_notification_dedup_check(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")
        db_mocks["get_last_notification_sent_at"].reset_mock()

        await flow.handle_callback(_SESSION, "comfort_view_another")

        db_mocks["get_last_notification_sent_at"].assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_crisis_gate_even_when_original_message_was_crisis_flagged(
        self, db_mocks, flow_store, classify_mock, crisis_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=True)
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I don't want to be here anymore.")
        await flow.handle_callback(_SESSION, "comfort_crisis_continue")
        crisis_notification_mock.reset_mock()

        reply = await flow.handle_callback(_SESSION, "comfort_view_another")

        crisis_notification_mock.assert_not_called()
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_skips_escalation_offer_even_when_conditions_still_met(
        self, db_mocks, flow_store, classify_mock, pastoral_outreach_notification_mock
    ) -> None:
        classify_mock.return_value = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.DESPAIR])
        db_mocks["count_recent_passages"].return_value = 11
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I keep asking for verses.")
        await flow.handle_callback(_SESSION, "comfort_escalation_yes")
        pastoral_outreach_notification_mock.assert_awaited_once()
        pastoral_outreach_notification_mock.reset_mock()

        reply = await flow.handle_callback(_SESSION, "comfort_view_another")

        pastoral_outreach_notification_mock.assert_not_called()
        assert reply is not None
        assert reply.text == _expected_verse_reply()

    @pytest.mark.asyncio
    async def test_new_reply_has_navigation_buttons_and_records_passage_flag(
        self, db_mocks, flow_store
    ) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        reply = await flow.handle_callback(_SESSION, "comfort_view_another")

        assert reply is not None
        assert reply.buttons == _navigation_buttons()
        assert reply.record_passage_on_success is True

    @pytest.mark.asyncio
    async def test_new_passage_recorded_only_after_confirm(self, db_mocks, flow_store, retrieve_passage_mock) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        retrieve_passage_mock.return_value = RetrievedPassage(
            reference="Romans 8:28", verse_text="Another verse.", verse_text_es="Otro verso.", is_fallback=False
        )
        await flow.handle_callback(_SESSION, "comfort_view_another")
        db_mocks["record_sent_passage"].assert_not_called()

        await flow.confirm_passage_sent(_SESSION)
        db_mocks["record_sent_passage"].assert_called_once_with(_UID, "Romans 8:28")


class TestConfirmPassageSent:
    """K-09: recording is deferred until the router confirms the reply was actually
    delivered — confirm_passage_sent is what performs that recording."""

    @pytest.mark.asyncio
    async def test_records_the_pending_passage(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")
        await flow.handle_text(_SESSION, "I've been feeling anxious lately.")

        await flow.confirm_passage_sent(_SESSION)

        db_mocks["record_sent_passage"].assert_called_once_with(_UID, "Psalm 23:4")

    @pytest.mark.asyncio
    async def test_no_active_flow_is_a_no_op(self, db_mocks, flow_store) -> None:
        await flow.confirm_passage_sent(_SESSION)
        db_mocks["record_sent_passage"].assert_not_called()

    @pytest.mark.asyncio
    async def test_state_without_a_pending_passage_is_a_no_op(self, db_mocks, flow_store) -> None:
        await flow.start(_SESSION, _UID, "en")  # step == "awaiting_text", no passage_reference yet
        await flow.confirm_passage_sent(_SESSION)
        db_mocks["record_sent_passage"].assert_not_called()
