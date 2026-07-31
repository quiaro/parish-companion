"""
Anonymized /comfort usage stats.

record_comfort_aggregate_stat's doesn't accept a telegram_user_id, session_id, or raw message text, so
there is no code path here that could persist a user identifier. The only "when" information
stored is a coarse local time-of-day bucket instead of a precise timestamp so there's no way
to correlate a row back to a specific request via server/webhook access logs.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from config import settings
from db.engine import SessionLocal
from db.models import ComfortAggregateStat

# (start_hour, end_hour, label) — end exclusive. Anything not covered (22:00-4:00,
# wrapping past midnight) falls through to "night".
_BUCKET_BOUNDARIES = [
    (4, 7, "dawn"),
    (7, 12, "morning"),
    (12, 18, "afternoon"),
    (18, 22, "evening"),
]


def _time_of_day_bucket(local_now: datetime) -> str:
    for start_hour, end_hour, label in _BUCKET_BOUNDARIES:
        if start_hour <= local_now.hour < end_hour:
            return label
    return "night"


def record_comfort_aggregate_stat(is_crisis: bool, emotional_tags: list[str], situational_tags: list[str]) -> None:
    local_now = datetime.now(ZoneInfo(settings.local_timezone))
    time_bucket = _time_of_day_bucket(local_now)
    with SessionLocal() as session:
        session.add(
            ComfortAggregateStat(
                is_crisis=is_crisis,
                emotional_tags=emotional_tags,
                situational_tags=situational_tags,
                time_bucket=time_bucket,
            )
        )
        session.commit()
