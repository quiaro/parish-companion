import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from commands.comfort.classifier import classify
from commands.comfort.constants import HIGH_RISK_EMOTIONAL_TAGS
from commands.comfort.models import ClassificationResult, FlowReply
from commands.comfort.notifications import send_crisis_notification, send_pastoral_outreach_notification
from config import settings
from db.parishioners import (
    count_recent_passages,
    ensure_parishioner,
    get_last_notification_sent_at,
    is_comfort_intro_shown,
    mark_comfort_intro_shown,
    record_notification_sent,
)
from translations import get_string

logger = logging.getLogger(__name__)

_COMFORT_KEY = "session:{}:comfort"
_MAX_INPUT_LENGTH = 2000

_CALLBACK_CRISIS_CONTINUE = "comfort_crisis_continue"
_CALLBACK_ESCALATION_YES = "comfort_escalation_yes"
_CALLBACK_ESCALATION_NO = "comfort_escalation_no"


async def _get_state(session_id: str) -> dict | None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            raw = await r.get(_COMFORT_KEY.format(session_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.error("comfort flow _get_state failed session=%s: %s", session_id, exc)
        return None


async def _set_state(session_id: str, state: dict) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.set(
                _COMFORT_KEY.format(session_id),
                json.dumps(state),
                ex=settings.session_ttl_seconds,
            )
    except Exception as exc:
        logger.error("comfort flow _set_state failed session=%s: %s", session_id, exc)


async def _clear_state(session_id: str) -> None:
    try:
        async with Redis.from_url(settings.redis_url, decode_responses=True) as r:
            await r.delete(_COMFORT_KEY.format(session_id))
    except Exception as exc:
        logger.error("comfort flow _clear_state failed session=%s: %s", session_id, exc)


async def _notification_dedup_passed(telegram_user_id: int) -> bool:
    """
    K-04: gates Steps D (crisis) and E (frequency escalation) so a parishioner who
    triggers both in quick succession within the dedup window doesn't get duplicate
    outreach. Passes if no notification has ever been sent, or the last one is strictly
    older than the cutoff window.
    """
    last_sent = await asyncio.to_thread(get_last_notification_sent_at, telegram_user_id)
    if last_sent is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.comfort_notification_dedup_window_hours)
    return last_sent < cutoff


async def _should_escalate(telegram_user_id: int, result: ClassificationResult) -> bool:
    """
    K-06: escalation requires a high-risk emotional tag AND a passage count strictly
    greater than the configured threshold within the frequency window. The tag check is
    cheap and in-memory, so it's checked first to avoid an unnecessary DB round trip.
    """
    if not any(tag in HIGH_RISK_EMOTIONAL_TAGS for tag in result.emotional_tags):
        return False
    count = await asyncio.to_thread(
        count_recent_passages, telegram_user_id, settings.comfort_frequency_window_hours
    )
    return count > settings.comfort_escalation_passage_threshold


def _serialize_classification(result: ClassificationResult) -> dict:
    return {
        "is_crisis": result.is_crisis,
        "emotional_tags": [t.value for t in result.emotional_tags],
        "situational_tags": [t.value for t in result.situational_tags],
    }


async def start(session_id: str, telegram_user_id: int, language: str = "en") -> str:
    await asyncio.to_thread(ensure_parishioner, telegram_user_id)

    if await asyncio.to_thread(is_comfort_intro_shown, telegram_user_id):
        reply = get_string("comfort_brief_intro", language)
    else:
        await asyncio.to_thread(mark_comfort_intro_shown, telegram_user_id)
        reply = get_string("comfort_intro", language)

    await _set_state(
        session_id,
        {"language": language, "telegram_user_id": telegram_user_id, "step": "awaiting_text"},
    )
    return reply


async def _enter_crisis_gate(
    session_id: str, telegram_user_id: int, language: str, result: ClassificationResult
) -> FlowReply:
    """K-05: pastoral message + urgent parish notification, gated behind Continue
    rather than sending a verse straight away."""
    if await send_crisis_notification(telegram_user_id, language):
        # Only recorded on success — a failed send must not close the K-04 dedup window,
        # or the next crisis message within it would silently skip retrying the parish alert.
        await asyncio.to_thread(record_notification_sent, telegram_user_id)
    await _set_state(
        session_id,
        {
            "language": language,
            "telegram_user_id": telegram_user_id,
            "step": "awaiting_crisis_response",
            "classification": _serialize_classification(result),
        },
    )
    return FlowReply(
        text=get_string("comfort_crisis_message", language),
        buttons=[(get_string("comfort_button_continue", language), _CALLBACK_CRISIS_CONTINUE)],
    )


async def _enter_escalation_gate(
    session_id: str, telegram_user_id: int, language: str, result: ClassificationResult
) -> FlowReply:
    """K-06: unlike the crisis gate, no notification is sent yet here — only if the
    parishioner taps Yes. Asking first, rather than notifying unconditionally, is the
    whole point of this being an offer rather than a hard escalation like K-05."""
    await _set_state(
        session_id,
        {
            "language": language,
            "telegram_user_id": telegram_user_id,
            "step": "awaiting_escalation_response",
            "classification": _serialize_classification(result),
        },
    )
    return FlowReply(
        text=get_string("comfort_escalation_message", language),
        buttons=[
            (get_string("comfort_button_yes", language), _CALLBACK_ESCALATION_YES),
            (get_string("comfort_button_no", language), _CALLBACK_ESCALATION_NO),
        ],
    )


async def handle_text(session_id: str, text: str) -> FlowReply | None:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("handle_text called with no active flow session=%s", session_id)
        return FlowReply(text=get_string("telegram_cmd_unknown", "en"))

    if state.get("step") != "awaiting_text":
        # A button tap is pending (e.g. crisis Continue, escalation Yes/No) — silently
        # ignore stray text.
        return None

    language = state["language"]
    telegram_user_id = state["telegram_user_id"]
    stripped = text.strip()

    if len(stripped) > _MAX_INPUT_LENGTH:
        return FlowReply(text=get_string("comfort_input_too_long", language))

    try:
        result = await classify(stripped)
    except Exception as exc:
        # Retrieval (Step F) isn't wired in yet, so nothing currently acts on the
        # classification result — don't let a classifier failure block the parishioner
        # from getting a reply.
        logger.error("classify failed session=%s: %s", session_id, exc)
        await _clear_state(session_id)
        return FlowReply(text=get_string("comfort_ack_placeholder", language))

    if not await _notification_dedup_passed(telegram_user_id):
        # K-04: Steps D and E skipped entirely; proceeds to Step F (not built yet).
        await _clear_state(session_id)
        return FlowReply(text=get_string("comfort_ack_placeholder", language))

    if result.is_crisis:
        return await _enter_crisis_gate(session_id, telegram_user_id, language, result)

    if await _should_escalate(telegram_user_id, result):
        return await _enter_escalation_gate(session_id, telegram_user_id, language, result)

    # is_crisis False, no escalation — proceeds to Step F (K-07, not built yet).
    await _clear_state(session_id)
    return FlowReply(text=get_string("comfort_ack_placeholder", language))


async def handle_callback(session_id: str, callback_data: str) -> FlowReply | None:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("handle_callback called with no active flow session=%s data=%s", session_id, callback_data)
        return None

    step = state.get("step")
    language = state["language"]

    if step == "awaiting_crisis_response" and callback_data == _CALLBACK_CRISIS_CONTINUE:
        # Step F (retrieval) isn't built yet — placeholder until K-07. Reuses the
        # classification already stored in state rather than reclassifying.
        await _clear_state(session_id)
        return FlowReply(text=get_string("comfort_ack_placeholder", language))

    if step == "awaiting_escalation_response" and callback_data in (
        _CALLBACK_ESCALATION_YES,
        _CALLBACK_ESCALATION_NO,
    ):
        if callback_data == _CALLBACK_ESCALATION_YES:
            telegram_user_id = state["telegram_user_id"]
            if await send_pastoral_outreach_notification(telegram_user_id, language):
                await asyncio.to_thread(record_notification_sent, telegram_user_id)
        # Either way (Yes or No), Step F (retrieval) isn't built yet — placeholder
        # until K-07, reusing the classification already stored in state.
        await _clear_state(session_id)
        return FlowReply(text=get_string("comfort_ack_placeholder", language))

    logger.warning(
        "handle_callback called with mismatched step=%s data=%s session=%s", step, callback_data, session_id
    )
    return None


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
