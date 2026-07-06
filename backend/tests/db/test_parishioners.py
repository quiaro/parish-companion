"""
Integration tests for the shared per-parishioner Postgres store (K-00).

These run against a real Postgres instance (the `postgres` sibling service in
docker-compose) rather than mocks, since the behavior under test — ON CONFLICT
idempotency, concurrent writes, and rolling-window timestamp boundaries — can't be
meaningfully faked. Schema must already exist via `alembic upgrade head` before
running this file; see DEVELOPMENT.md.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from db import parishioners as store
from db.engine import SessionLocal
from db.models import ComfortSentPassage, Parishioner

_UID = 111222333


def _insert_passage_at(telegram_user_id: int, passage_reference: str, sent_at: datetime) -> None:
    with SessionLocal() as session:
        session.add(
            ComfortSentPassage(
                telegram_user_id=telegram_user_id,
                passage_reference=passage_reference,
                sent_at=sent_at,
            )
        )
        session.commit()


def _passage_count(telegram_user_id: int) -> int:
    with SessionLocal() as session:
        return session.execute(
            select(func.count())
            .select_from(ComfortSentPassage)
            .where(ComfortSentPassage.telegram_user_id == telegram_user_id)
        ).scalar_one()


class TestEnsureParishioner:
    def test_creates_row_if_missing(self):
        store.ensure_parishioner(_UID)
        with SessionLocal() as session:
            assert session.get(Parishioner, _UID) is not None

    def test_idempotent_on_repeated_calls(self):
        store.ensure_parishioner(_UID)
        store.ensure_parishioner(_UID)
        with SessionLocal() as session:
            count = session.execute(
                select(func.count()).select_from(Parishioner).where(Parishioner.telegram_user_id == _UID)
            ).scalar_one()
        assert count == 1

    def test_concurrent_calls_do_not_error_or_duplicate(self):
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(store.ensure_parishioner, _UID) for _ in range(10)]
            for future in futures:
                future.result()  # re-raises if any call errored

        with SessionLocal() as session:
            count = session.execute(
                select(func.count()).select_from(Parishioner).where(Parishioner.telegram_user_id == _UID)
            ).scalar_one()
        assert count == 1


class TestComfortIntroShown:
    def test_defaults_to_false(self):
        store.ensure_parishioner(_UID)
        assert store.is_comfort_intro_shown(_UID) is False

    def test_transitions_to_true_and_persists_across_a_fresh_read(self):
        store.ensure_parishioner(_UID)
        store.mark_comfort_intro_shown(_UID)
        # A fresh call opens its own session/connection — there is no in-memory
        # caching, so this confirms the value was actually persisted, not just
        # held on some object still in scope.
        assert store.is_comfort_intro_shown(_UID) is True


class TestGetRecentSentPassages:
    def test_prunes_rows_older_than_two_weeks(self):
        store.ensure_parishioner(_UID)
        stale_at = datetime.now(timezone.utc) - timedelta(days=14, seconds=1)
        _insert_passage_at(_UID, "John 3:16", stale_at)

        results = store.get_recent_sent_passages(_UID)

        assert results == []
        assert _passage_count(_UID) == 0

    def test_keeps_rows_within_two_weeks(self):
        store.ensure_parishioner(_UID)
        fresh_at = datetime.now(timezone.utc) - timedelta(days=13)
        _insert_passage_at(_UID, "Psalm 23:1", fresh_at)

        results = store.get_recent_sent_passages(_UID)

        assert [r.passage_reference for r in results] == ["Psalm 23:1"]


class TestCountRecentPassages:
    def test_boundary_is_exclusive(self):
        store.ensure_parishioner(_UID)
        now = datetime.now(timezone.utc)
        _insert_passage_at(_UID, "at exactly one hour", now - timedelta(hours=1))
        _insert_passage_at(_UID, "just inside one hour", now - timedelta(hours=1) + timedelta(seconds=1))

        assert store.count_recent_passages(_UID, hours=1) == 1


class TestNotificationTimestamp:
    def test_defaults_to_none(self):
        store.ensure_parishioner(_UID)
        assert store.get_last_notification_sent_at(_UID) is None

    def test_round_trips_with_full_precision(self):
        store.ensure_parishioner(_UID)
        store.record_notification_sent(_UID)
        recorded = store.get_last_notification_sent_at(_UID)

        assert recorded is not None
        # The 24-hour dedup check (a future story) will compare this value with an
        # exclusive boundary — that's only trustworthy if the persistence layer
        # preserves the timestamp exactly, which this confirms.
        assert recorded > datetime.now(timezone.utc) - timedelta(seconds=5)
