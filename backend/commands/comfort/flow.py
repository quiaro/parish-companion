import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from commands.comfort.classifier import classify
from commands.comfort.constants import HIGH_RISK_EMOTIONAL_TAGS
from commands.comfort.framing import frame_passage
from commands.comfort.localization import localize_reference
from commands.comfort.models import ClassificationResult, EmotionalTag, FlowReply, SituationalTag
from commands.comfort.notifications import send_crisis_notification, send_pastoral_outreach_notification
from commands.comfort.retrieval import retrieve_passage
from config import settings
from db.parishioners import (
    count_recent_passages,
    ensure_parishioner,
    get_last_notification_sent_at,
    is_comfort_intro_shown,
    mark_comfort_intro_shown,
    record_notification_sent,
    record_sent_passage,
)
from translations import get_string

logger = logging.getLogger(__name__)

_COMFORT_KEY = "session:{}:comfort"
_MAX_INPUT_LENGTH = 2000

_CALLBACK_CRISIS_CONTINUE = "comfort_crisis_continue"
_CALLBACK_ESCALATION_YES = "comfort_escalation_yes"
_CALLBACK_ESCALATION_NO = "comfort_escalation_no"
_CALLBACK_VIEW_ANOTHER = "comfort_view_another"
_CALLBACK_EXIT = "comfort_exit"


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


def _deserialize_classification(data: dict) -> ClassificationResult:
    return ClassificationResult(
        is_crisis=data["is_crisis"],
        emotional_tags=[EmotionalTag(t) for t in data["emotional_tags"]],
        situational_tags=[SituationalTag(t) for t in data["situational_tags"]],
    )


async def _complete_with_retrieval(
    session_id: str, telegram_user_id: int, language: str, raw_text: str, result: ClassificationResult
) -> FlowReply:
    """Step F/G/H: retrieves a passage and frames it (skipped entirely on the Step G
    fallback path). This is the terminal step of every path once notification gating
    is resolved. Flow state is kept alive (not cleared) so passage is recorded once 
    the send is confirmed. "View another passage" restarts retrieval without reclassifying, 
    "Exit" finally clears the flow state."""
    passage = await retrieve_passage(telegram_user_id, raw_text, result)
    # Localized once — passage.reference itself stays English throughout (it's
    # the canonical key used for DB history and Qdrant point IDs). Only what's
    # shown to the parishioner is localized.
    localized_reference = localize_reference(passage.reference, language)
    localized_verse_text = passage.verse_text_es if language == "es" else passage.verse_text

    if passage.is_fallback:
        text = get_string("comfort_fallback_message", language).format(
            reference=localized_reference, verse_text=localized_verse_text
        )
    else:
        try:
            framing = await frame_passage(raw_text, localized_reference, localized_verse_text, language)
        except Exception as exc:
            # A framing failure shouldn't block the parishioner from getting the verse
            # itself — same "don't let an LLM hiccup block the reply" principle as classify().
            logger.error("frame_passage failed session=%s: %s", session_id, exc)
            text = get_string("comfort_verse_reply_no_framing", language).format(
                reference=localized_reference, verse_text=localized_verse_text
            )
        else:
            text = get_string("comfort_verse_reply", language).format(
                framing=framing, reference=localized_reference, verse_text=localized_verse_text
            )

    await _set_state(
        session_id,
        {
            "language": language,
            "telegram_user_id": telegram_user_id,
            "step": "awaiting_navigation",
            "raw_text": raw_text,
            "classification": _serialize_classification(result),
            "passage_reference": passage.reference,
        },
    )
    return FlowReply(
        text=text,
        buttons=[
            (get_string("comfort_button_view_another", language), _CALLBACK_VIEW_ANOTHER),
            (get_string("comfort_button_exit", language), _CALLBACK_EXIT),
        ],
        record_passage_on_success=True,
    )


async def confirm_passage_sent(session_id: str) -> None:
    """K-09: called by the router only after send_message confirms the verse reply was
    actually delivered using the reference held in flow state."""
    state = await _get_state(session_id)
    if state is None:
        logger.warning("confirm_passage_sent called with no active flow session=%s", session_id)
        return
    if "passage_reference" not in state:
        logger.warning("confirm_passage_sent called with no passage in session=%s", session_id)
        return
    await asyncio.to_thread(record_sent_passage, state["telegram_user_id"], state["passage_reference"])


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
    session_id: str, telegram_user_id: int, language: str, raw_text: str, result: ClassificationResult
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
            "raw_text": raw_text,
            "classification": _serialize_classification(result),
        },
    )
    return FlowReply(
        text=get_string("comfort_crisis_message", language),
        buttons=[(get_string("comfort_button_continue", language), _CALLBACK_CRISIS_CONTINUE)],
    )


async def _enter_escalation_gate(
    session_id: str, telegram_user_id: int, language: str, raw_text: str, result: ClassificationResult
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
            "raw_text": raw_text,
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
        # No classification available at all, so retrieval can't run intelligently —
        # don't let a classifier failure block the parishioner from getting a reply.
        logger.error("classify failed session=%s: %s", session_id, exc)
        await _clear_state(session_id)
        return FlowReply(text=get_string("comfort_ack_placeholder", language))

    if not await _notification_dedup_passed(telegram_user_id):
        # K-04: Steps D and E skipped entirely; proceeds directly to Step F.
        return await _complete_with_retrieval(session_id, telegram_user_id, language, stripped, result)

    if result.is_crisis:
        return await _enter_crisis_gate(session_id, telegram_user_id, language, stripped, result)

    if await _should_escalate(telegram_user_id, result):
        return await _enter_escalation_gate(session_id, telegram_user_id, language, stripped, result)

    # is_crisis False, no escalation — proceeds to Step F.
    return await _complete_with_retrieval(session_id, telegram_user_id, language, stripped, result)


async def handle_callback(session_id: str, callback_data: str) -> FlowReply | None:
    state = await _get_state(session_id)
    if state is None:
        logger.warning("handle_callback called with no active flow session=%s data=%s", session_id, callback_data)
        return None

    step = state.get("step")
    language = state["language"]

    if step == "awaiting_crisis_response" and callback_data == _CALLBACK_CRISIS_CONTINUE:
        # Reuses the classification and raw text already stored in state rather than
        # reclassifying.
        telegram_user_id = state["telegram_user_id"]
        result = _deserialize_classification(state["classification"])
        return await _complete_with_retrieval(session_id, telegram_user_id, language, state["raw_text"], result)

    if step == "awaiting_escalation_response" and callback_data in (
        _CALLBACK_ESCALATION_YES,
        _CALLBACK_ESCALATION_NO,
    ):
        telegram_user_id = state["telegram_user_id"]
        if callback_data == _CALLBACK_ESCALATION_YES:
            if await send_pastoral_outreach_notification(telegram_user_id, language):
                await asyncio.to_thread(record_notification_sent, telegram_user_id)
        # Either way (Yes or No), retrieval proceeds using the classification and raw
        # text already stored in state rather than reclassifying.
        result = _deserialize_classification(state["classification"])
        return await _complete_with_retrieval(session_id, telegram_user_id, language, state["raw_text"], result)

    if step == "awaiting_navigation" and callback_data == _CALLBACK_VIEW_ANOTHER:
        # Skips Step C/D/E entirely (dedup, crisis gate, escalation offer). The
        # parishioner already passed through gating once for this message, so asking
        # for another verse shouldn't re-surface the crisis gate or a parish
        # notification. Straight to Step F/G/H, reusing the stored raw_text/classification.
        telegram_user_id = state["telegram_user_id"]
        result = _deserialize_classification(state["classification"])
        return await _complete_with_retrieval(session_id, telegram_user_id, language, state["raw_text"], result)

    if step == "awaiting_navigation" and callback_data == _CALLBACK_EXIT:
        await _clear_state(session_id)
        return FlowReply(text=get_string("telegram_cmd_help", "en"))

    logger.warning(
        "handle_callback called with mismatched step=%s data=%s session=%s", step, callback_data, session_id
    )
    return None


async def get_state(session_id: str) -> dict | None:
    return await _get_state(session_id)
