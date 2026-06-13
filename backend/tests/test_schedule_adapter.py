from collections import defaultdict
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import gspread
import pytest

from schedules import (
    CachedScheduleAdapter,
    Language,
    ParishSchedule,
    ScheduleEntry,
    ScheduleType,
    ScheduleUnavailableError,
    StaticScheduleAdapter,
)
from schedules.google_sheets import GoogleSheetsScheduleAdapter


# ---------------------------------------------------------------------------
# StaticScheduleAdapter
# ---------------------------------------------------------------------------

class TestStaticScheduleAdapter:
    def test_returns_parish_schedule(self):
        adapter = StaticScheduleAdapter()
        result = adapter.get_schedule()
        assert isinstance(result, ParishSchedule)

    def test_default_schedule_has_mass_entries(self):
        result = StaticScheduleAdapter().get_schedule()
        assert any(e.type == ScheduleType.MASS for e in result.regular)

    def test_default_schedule_has_confession_entries(self):
        result = StaticScheduleAdapter().get_schedule()
        assert any(e.type == ScheduleType.CONFESSION for e in result.regular)

    def test_default_schedule_languages_are_language_enums(self):
        result = StaticScheduleAdapter().get_schedule()
        languages = {e.language for e in result.regular if e.language is not None}
        assert languages <= {Language.EN, Language.ES}

    def test_default_schedule_has_no_special(self):
        adapter = StaticScheduleAdapter()
        result = adapter.get_schedule()
        assert result.special is None

    def test_custom_schedule_is_returned_as_is(self):
        custom = ParishSchedule(
            regular=[ScheduleEntry(type=ScheduleType.MASS, day="Monday", start_time="07:00")]
        )
        adapter = StaticScheduleAdapter(schedule=custom)
        assert adapter.get_schedule() is custom


# ---------------------------------------------------------------------------
# CachedScheduleAdapter
# ---------------------------------------------------------------------------

class TestCachedScheduleAdapter:
    def _make_inner(self, schedule: ParishSchedule | None = None) -> MagicMock:
        inner = MagicMock()
        inner.get_schedule.return_value = schedule or ParishSchedule()
        return inner

    def test_calls_inner_on_first_request(self):
        inner = self._make_inner()
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)
        adapter.get_schedule()
        inner.get_schedule.assert_called_once()

    def test_returns_cached_result_on_second_request(self):
        inner = self._make_inner()
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)
        first = adapter.get_schedule()
        second = adapter.get_schedule()
        assert first is second
        inner.get_schedule.assert_called_once()

    def test_refreshes_after_ttl_expires(self):
        inner = self._make_inner()
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)

        with patch("schedules.cache.time.time", return_value=0.0):
            adapter.get_schedule()

        with patch("schedules.cache.time.time", return_value=61.0):
            adapter.get_schedule()

        assert inner.get_schedule.call_count == 2

    def test_does_not_refresh_before_ttl_expires(self):
        inner = self._make_inner()
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)

        with patch("schedules.cache.time.time", return_value=0.0):
            adapter.get_schedule()

        with patch("schedules.cache.time.time", return_value=59.0):
            adapter.get_schedule()

        inner.get_schedule.assert_called_once()

    def test_propagates_schedule_unavailable_error(self):
        inner = MagicMock()
        inner.get_schedule.side_effect = ScheduleUnavailableError("unreachable")
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)
        with pytest.raises(ScheduleUnavailableError):
            adapter.get_schedule()

    def test_leaves_cache_empty_when_inner_raises(self):
        inner = MagicMock()
        inner.get_schedule.side_effect = ScheduleUnavailableError("unreachable")
        adapter = CachedScheduleAdapter(inner, ttl_seconds=60)

        with pytest.raises(ScheduleUnavailableError):
            adapter.get_schedule()

        inner.get_schedule.side_effect = None
        inner.get_schedule.return_value = ParishSchedule()
        result = adapter.get_schedule()
        assert isinstance(result, ParishSchedule)


# ---------------------------------------------------------------------------
# GoogleSheetsScheduleAdapter — special schedule picker logic
# ---------------------------------------------------------------------------

def _make_groups(schedules: list[tuple[str, date, date, list[ScheduleEntry]]]):
    groups = defaultdict(list)
    for name, start, end, entries in schedules:
        groups[(name, start, end)].extend(entries)
    return dict(groups)


_ENTRY = ScheduleEntry(type=ScheduleType.MASS, day="Sunday", start_time="10:00")


class TestPickRelevantSchedule:
    today = date.today()

    def test_returns_none_when_no_schedules(self):
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule({})
        assert result is None

    def test_returns_none_when_all_past(self):
        groups = _make_groups([
            ("Easter", self.today - timedelta(days=10), self.today - timedelta(days=3), [_ENTRY]),
        ])
        assert GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups) is None

    def test_returns_none_when_upcoming_beyond_window(self):
        groups = _make_groups([
            ("Christmas", self.today + timedelta(days=8), self.today + timedelta(days=14), [_ENTRY]),
        ])
        assert GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups) is None

    def test_returns_active_schedule(self):
        groups = _make_groups([
            ("Holy Week", self.today - timedelta(days=2), self.today + timedelta(days=5), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Holy Week"

    def test_returns_upcoming_within_window(self):
        groups = _make_groups([
            ("Advent", self.today + timedelta(days=5), self.today + timedelta(days=12), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Advent"

    def test_active_takes_precedence_over_upcoming(self):
        groups = _make_groups([
            ("Holy Week", self.today - timedelta(days=1), self.today + timedelta(days=6), [_ENTRY]),
            ("First Friday", self.today + timedelta(days=2), self.today + timedelta(days=2), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Holy Week"

    def test_most_recently_started_active_wins(self):
        groups = _make_groups([
            ("Older", self.today - timedelta(days=5), self.today + timedelta(days=2), [_ENTRY]),
            ("Newer", self.today - timedelta(days=1), self.today + timedelta(days=4), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Newer"

    def test_soonest_upcoming_wins(self):
        groups = _make_groups([
            ("Farther", self.today + timedelta(days=6), self.today + timedelta(days=8), [_ENTRY]),
            ("Closer", self.today + timedelta(days=3), self.today + timedelta(days=5), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Closer"

    def test_active_schedule_on_start_date(self):
        groups = _make_groups([
            ("Today", self.today, self.today + timedelta(days=3), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Today"

    def test_active_schedule_on_end_date(self):
        groups = _make_groups([
            ("Ending Today", self.today - timedelta(days=3), self.today, [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Ending Today"

    def test_upcoming_schedule_on_window_boundary(self):
        groups = _make_groups([
            ("Boundary", self.today + timedelta(days=7), self.today + timedelta(days=10), [_ENTRY]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert result.name == "Boundary"

    def test_schedule_just_outside_window_is_excluded(self):
        groups = _make_groups([
            ("Too Far", self.today + timedelta(days=8), self.today + timedelta(days=12), [_ENTRY]),
        ])
        assert GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups) is None

    def test_entries_are_attached_to_returned_schedule(self):
        entry = ScheduleEntry(type=ScheduleType.CONFESSION, day="Friday", start_time="18:00")
        groups = _make_groups([
            ("Holy Week", self.today - timedelta(days=1), self.today + timedelta(days=5), [entry]),
        ])
        result = GoogleSheetsScheduleAdapter._pick_relevant_schedule(groups)
        assert result is not None
        assert entry in result.entries


# ---------------------------------------------------------------------------
# GoogleSheetsScheduleAdapter — _parse_entry
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return GoogleSheetsScheduleAdapter("fake-id", "fake-path")


def _row(**kwargs) -> dict:
    return {"Type": "mass", "Day": "Sunday", "Time": "10:00", "End Time": "", "Language": "", "Notes": "", **kwargs}


class TestParseEntry:
    def test_valid_mass_row(self, adapter):
        entry = adapter._parse_entry(_row(Type="mass"))
        assert entry is not None
        assert entry.type == ScheduleType.MASS

    def test_valid_confession_row(self, adapter):
        entry = adapter._parse_entry(_row(Type="confession"))
        assert entry is not None
        assert entry.type == ScheduleType.CONFESSION

    def test_day_and_start_time_are_set(self, adapter):
        entry = adapter._parse_entry(_row(Day="Saturday", Time="16:00"))
        assert entry is not None
        assert entry.day == "Saturday"
        assert entry.start_time == "16:00"

    def test_end_time_is_set_when_present(self, adapter):
        entry = adapter._parse_entry(_row(**{"End Time": "11:00"}))
        assert entry is not None
        assert entry.end_time == "11:00"

    def test_end_time_is_none_when_empty(self, adapter):
        entry = adapter._parse_entry(_row(**{"End Time": ""}))
        assert entry is not None
        assert entry.end_time is None

    def test_language_is_parsed_to_enum(self, adapter):
        entry = adapter._parse_entry(_row(Language="en"))
        assert entry is not None
        assert entry.language == Language.EN

    def test_language_is_none_when_empty(self, adapter):
        entry = adapter._parse_entry(_row(Language=""))
        assert entry is not None
        assert entry.language is None

    def test_unknown_language_sets_none_but_keeps_entry(self, adapter):
        entry = adapter._parse_entry(_row(Language="fr"))
        assert entry is not None
        assert entry.language is None

    def test_notes_are_set_when_present(self, adapter):
        entry = adapter._parse_entry(_row(Notes="Bilingual"))
        assert entry is not None
        assert entry.notes == "Bilingual"

    def test_notes_are_none_when_empty(self, adapter):
        entry = adapter._parse_entry(_row(Notes=""))
        assert entry is not None
        assert entry.notes is None

    def test_unknown_type_returns_none(self, adapter):
        entry = adapter._parse_entry(_row(Type="adoration"))
        assert entry is None

    def test_type_value_is_case_insensitive(self, adapter):
        entry = adapter._parse_entry(_row(Type="MASS"))
        assert entry is not None
        assert entry.type == ScheduleType.MASS


# ---------------------------------------------------------------------------
# GoogleSheetsScheduleAdapter — _read_special
# ---------------------------------------------------------------------------

def _special_rows(name: str, start: date, end: date, extra: list[dict] | None = None) -> list[dict]:
    base = [
        {
            "Name": name,
            "Start Date": start.isoformat(),
            "End Date": end.isoformat(),
            "Type": "mass",
            "Day": "Sunday",
            "Time": "10:00",
            "End Time": "",
            "Language": "",
            "Notes": "",
        }
    ]
    return base + (extra or [])


def _mock_spreadsheet(rows: list[dict]) -> MagicMock:
    worksheet = MagicMock()
    worksheet.get_all_records.return_value = rows
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet
    return spreadsheet


class TestReadSpecial:
    today = date.today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=6)

    def test_returns_none_when_tab_missing(self, adapter):
        spreadsheet = MagicMock()
        spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound
        assert adapter._read_special(spreadsheet) is None

    def test_returns_none_when_tab_is_empty(self, adapter):
        assert adapter._read_special(_mock_spreadsheet([])) is None

    def test_returns_none_when_schedule_outside_window(self, adapter):
        rows = _special_rows(
            "Far Future",
            self.today + timedelta(days=8),
            self.today + timedelta(days=14),
        )
        assert adapter._read_special(_mock_spreadsheet(rows)) is None

    def test_parses_active_special_schedule(self, adapter):
        rows = _special_rows("Holy Week", self.start, self.end)
        result = adapter._read_special(_mock_spreadsheet(rows))
        assert result is not None
        assert result.name == "Holy Week"
        assert result.start_date == self.start
        assert result.end_date == self.end

    def test_groups_multiple_entries_under_one_schedule(self, adapter):
        extra_row = {
            "Name": "Holy Week",
            "Start Date": self.start.isoformat(),
            "End Date": self.end.isoformat(),
            "Type": "confession",
            "Day": "Friday",
            "Time": "18:00",
            "End Time": "",
            "Language": "",
            "Notes": "",
        }
        rows = _special_rows("Holy Week", self.start, self.end, extra=[extra_row])
        result = adapter._read_special(_mock_spreadsheet(rows))
        assert result is not None
        assert len(result.entries) == 2
        types = {e.type for e in result.entries}
        assert types == {ScheduleType.MASS, ScheduleType.CONFESSION}

    def test_skips_rows_with_unparseable_dates(self, adapter):
        rows = [
            {
                "Name": "Holy Week",
                "Start Date": "not-a-date",
                "End Date": self.end.isoformat(),
                "Type": "mass",
                "Day": "Sunday",
                "Time": "10:00",
                "End Time": "",
                "Language": "",
                "Notes": "",
            }
        ]
        assert adapter._read_special(_mock_spreadsheet(rows)) is None

    def test_skips_rows_missing_required_fields(self, adapter):
        missing_name = [{"Name": "", "Start Date": self.start.isoformat(), "End Date": self.end.isoformat(),
                         "Type": "mass", "Day": "Sunday", "Time": "10:00", "End Time": "", "Language": "", "Notes": ""}]
        assert adapter._read_special(_mock_spreadsheet(missing_name)) is None

        missing_type = [{"Name": "Holy Week", "Start Date": self.start.isoformat(), "End Date": self.end.isoformat(),
                         "Type": "", "Day": "Sunday", "Time": "10:00", "End Time": "", "Language": "", "Notes": ""}]
        assert adapter._read_special(_mock_spreadsheet(missing_type)) is None
