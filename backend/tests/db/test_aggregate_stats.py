"""
Integration tests for usage stats run against a real Postgres instance.
"""

from sqlalchemy import inspect, select

from db.aggregate_stats import record_comfort_aggregate_stat
from db.engine import SessionLocal
from db.models import ComfortAggregateStat


def _all_rows() -> list[ComfortAggregateStat]:
    with SessionLocal() as session:
        return list(session.execute(select(ComfortAggregateStat)).scalars().all())


class TestRecordComfortAggregateStat:
    def test_records_a_row_with_the_given_fields(self) -> None:
        record_comfort_aggregate_stat(True, ["despair", "hopelessness"], ["bereavement"])

        rows = _all_rows()
        assert len(rows) == 1
        assert rows[0].is_crisis is True
        assert rows[0].emotional_tags == ["despair", "hopelessness"]
        assert rows[0].situational_tags == ["bereavement"]
        assert rows[0].time_bucket in {"dawn", "morning", "afternoon", "evening", "night"}

    def test_records_non_crisis_message_with_empty_tags(self) -> None:
        record_comfort_aggregate_stat(False, [], [])

        rows = _all_rows()
        assert len(rows) == 1
        assert rows[0].is_crisis is False
        assert rows[0].emotional_tags == []
        assert rows[0].situational_tags == []

    def test_multiple_calls_each_record_a_separate_row(self) -> None:
        record_comfort_aggregate_stat(True, ["despair"], [])
        record_comfort_aggregate_stat(False, ["joy"], [])

        assert len(_all_rows()) == 2


class TestNoIdentifyingColumns:
    def test_table_has_no_identifying_or_precise_timestamp_columns(self) -> None:
        # Structural safety check. This asserts on the actual schema so a future column 
        # addition can't silently reintroduce an identifier or a precise, joinable timestamp.
        columns = {c.name for c in inspect(ComfortAggregateStat).columns}
        assert columns == {"id", "is_crisis", "emotional_tags", "situational_tags", "time_bucket"}
