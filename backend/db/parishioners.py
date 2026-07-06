from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from db.engine import SessionLocal
from db.models import ComfortSentPassage, Parishioner

_PASSAGE_HISTORY_WINDOW = timedelta(days=14)


@dataclass
class SentPassage:
    passage_reference: str
    sent_at: datetime


def ensure_parishioner(telegram_user_id: int) -> None:
    """Create a parishioners row if one doesn't exist. Idempotent and safe under concurrent calls."""
    stmt = insert(Parishioner).values(telegram_user_id=telegram_user_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["telegram_user_id"])
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def is_comfort_intro_shown(telegram_user_id: int) -> bool:
    with SessionLocal() as session:
        return bool(
            session.execute(
                select(Parishioner.comfort_intro_shown).where(Parishioner.telegram_user_id == telegram_user_id)
            ).scalar_one()
        )


def mark_comfort_intro_shown(telegram_user_id: int) -> None:
    with SessionLocal() as session:
        parishioner = session.get(Parishioner, telegram_user_id)
        if parishioner is None:
            # Fail fast with a clear error if the parishioner row doesn't exist.
            raise ValueError(f"ensure_parishioner({telegram_user_id}) must be called first")
        parishioner.comfort_intro_shown = True
        parishioner.updated_at = datetime.now(timezone.utc)
        session.commit()


def record_sent_passage(telegram_user_id: int, passage_reference: str) -> None:
    with SessionLocal() as session:
        session.add(ComfortSentPassage(telegram_user_id=telegram_user_id, passage_reference=passage_reference))
        session.commit()


def get_recent_sent_passages(telegram_user_id: int) -> list[SentPassage]:
    """
    The single accessor for comfort_sent_passages: prunes this parishioner's rows older
    than 2 weeks, then returns what's left. No other code path should query this table
    directly, so pruning can't be accidentally skipped by a future caller.
    """
    cutoff = datetime.now(timezone.utc) - _PASSAGE_HISTORY_WINDOW
    with SessionLocal() as session:
        session.execute(
            delete(ComfortSentPassage).where(
                ComfortSentPassage.telegram_user_id == telegram_user_id,
                ComfortSentPassage.sent_at <= cutoff,
            )
        )
        session.commit()
        rows = session.execute(
            select(ComfortSentPassage.passage_reference, ComfortSentPassage.sent_at)
            .where(ComfortSentPassage.telegram_user_id == telegram_user_id)
            .order_by(ComfortSentPassage.sent_at)
        ).all()
    return [SentPassage(passage_reference=row.passage_reference, sent_at=row.sent_at) for row in rows]


def count_recent_passages(telegram_user_id: int, hours: int = 1) -> int:
    """Counts passages sent within the past rolling `hours`, exclusive at the boundary."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    passages = get_recent_sent_passages(telegram_user_id)
    return sum(1 for p in passages if p.sent_at > cutoff)


def get_last_notification_sent_at(telegram_user_id: int) -> datetime | None:
    with SessionLocal() as session:
        return session.execute(
            select(Parishioner.comfort_last_notification_sent_at).where(
                Parishioner.telegram_user_id == telegram_user_id
            )
        ).scalar_one()


def record_notification_sent(telegram_user_id: int) -> None:
    with SessionLocal() as session:
        parishioner = session.get(Parishioner, telegram_user_id)
        if parishioner is None:
            # Fail fast with a clear error if the parishioner row doesn't exist.
            raise ValueError(f"ensure_parishioner({telegram_user_id}) must be called first")
        now = datetime.now(timezone.utc)
        parishioner.comfort_last_notification_sent_at = now
        parishioner.updated_at = now
        session.commit()
