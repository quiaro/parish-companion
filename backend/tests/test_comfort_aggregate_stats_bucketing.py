"""Unit tests for the local time-of-day bucketing used by anonymized /comfort stats. No DB access needed."""

from datetime import datetime

from db.aggregate_stats import _time_of_day_bucket


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, 30, hour, minute)


class TestTimeOfDayBucket:
    def test_dawn_lower_boundary(self) -> None:
        assert _time_of_day_bucket(_at(4, 0)) == "dawn"

    def test_dawn_upper_boundary_is_exclusive(self) -> None:
        assert _time_of_day_bucket(_at(6, 59)) == "dawn"
        assert _time_of_day_bucket(_at(7, 0)) == "morning"

    def test_morning(self) -> None:
        assert _time_of_day_bucket(_at(9, 30)) == "morning"

    def test_morning_upper_boundary_is_exclusive(self) -> None:
        assert _time_of_day_bucket(_at(11, 59)) == "morning"
        assert _time_of_day_bucket(_at(12, 0)) == "afternoon"

    def test_afternoon(self) -> None:
        assert _time_of_day_bucket(_at(15, 0)) == "afternoon"

    def test_afternoon_upper_boundary_is_exclusive(self) -> None:
        assert _time_of_day_bucket(_at(17, 59)) == "afternoon"
        assert _time_of_day_bucket(_at(18, 0)) == "evening"

    def test_evening(self) -> None:
        assert _time_of_day_bucket(_at(20, 0)) == "evening"

    def test_evening_upper_boundary_is_exclusive(self) -> None:
        assert _time_of_day_bucket(_at(21, 59)) == "evening"
        assert _time_of_day_bucket(_at(22, 0)) == "night"

    def test_night_wraps_past_midnight(self) -> None:
        assert _time_of_day_bucket(_at(23, 0)) == "night"
        assert _time_of_day_bucket(_at(0, 0)) == "night"
        assert _time_of_day_bucket(_at(3, 59)) == "night"
