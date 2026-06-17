from datetime import date, timedelta

import pytest

from commands.schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType, ScheduleUnavailableError, SpecialSchedule
from telegram.schedule import format_schedule, handle_schedules


def _mass(day: str, time: str, lang: Language | None = None) -> ScheduleEntry:
    return ScheduleEntry(type=ScheduleType.MASS, day=day, start_time=time, language=lang)


def _confession(day: str, start: str, end: str | None = None) -> ScheduleEntry:
    return ScheduleEntry(type=ScheduleType.CONFESSION, day=day, start_time=start, end_time=end)


# ---------------------------------------------------------------------------
# Time formatting
# ---------------------------------------------------------------------------

def test_on_the_hour_omits_minutes() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    result = format_schedule(schedule, "en")
    assert "9 AM" in result


def test_with_minutes_includes_them() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:30")])
    result = format_schedule(schedule, "en")
    assert "9:30 AM" in result


def test_pm_conversion() -> None:
    schedule = ParishSchedule(regular=[_mass("Saturday", "18:00")])
    result = format_schedule(schedule, "en")
    assert "6 PM" in result


def test_noon_is_pm() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "12:00")])
    result = format_schedule(schedule, "en")
    assert "12 PM" in result


def test_time_range_uses_en_dash() -> None:
    schedule = ParishSchedule(regular=[_confession("Saturday", "16:00", "18:00")])
    result = format_schedule(schedule, "en")
    assert "4 PM–6 PM" in result


# ---------------------------------------------------------------------------
# Mass section (S-01)
# ---------------------------------------------------------------------------

def test_mass_header_present_in_english() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    assert "Mass Times" in format_schedule(schedule, "en")


def test_mass_header_present_in_spanish() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    assert "Horarios de Misa" in format_schedule(schedule, "es")


def test_mass_day_shown_in_response_language() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    assert "Sunday" in format_schedule(schedule, "en")
    assert "Domingo" in format_schedule(schedule, "es")


def test_day_name_normalised_regardless_of_input_language() -> None:
    """'Domingo' in the data should display as 'Sunday' when language='en'."""
    schedule = ParishSchedule(regular=[_mass("Domingo", "09:00")])
    assert "Sunday" in format_schedule(schedule, "en")


def test_language_label_shown_in_english() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Sunday", "09:00", Language.EN),
        _mass("Sunday", "11:00", Language.ES),
    ])
    result = format_schedule(schedule, "en")
    assert "English" in result
    assert "Spanish" in result


def test_language_label_shown_in_spanish() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Sunday", "09:00", Language.EN),
        _mass("Sunday", "11:00", Language.ES),
    ])
    result = format_schedule(schedule, "es")
    assert "inglés" in result
    assert "español" in result


def test_multiple_masses_same_day_on_one_line() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Sunday", "09:00", Language.EN),
        _mass("Sunday", "11:00", Language.ES),
    ])
    result = format_schedule(schedule, "en")
    lines = [l for l in result.splitlines() if "Sunday" in l]
    assert len(lines) == 1
    assert "9 AM" in lines[0] and "11 AM" in lines[0]


def test_days_appear_in_week_order() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Saturday", "18:00"),
        _mass("Sunday", "09:00"),
    ])
    result = format_schedule(schedule, "en")
    assert result.index("Sunday") < result.index("Saturday")


def test_no_language_label_when_not_set() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    result = format_schedule(schedule, "en")
    assert "English" not in result
    assert "Spanish" not in result


# ---------------------------------------------------------------------------
# Confession section (S-02)
# ---------------------------------------------------------------------------

def test_confession_header_present_in_english() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    assert "Confession" in format_schedule(schedule, "en")


def test_confession_header_present_in_spanish() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    assert "Confesiones" in format_schedule(schedule, "es")


def test_confession_times_appear_below_mass_times() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Sunday", "09:00"),
        _confession("Saturday", "16:00", "18:00"),
    ])
    result = format_schedule(schedule, "en")
    assert result.index("Mass Times") < result.index("Confession")
    assert result.index("Confession") < result.index("Saturday: 4 PM")


def test_confession_section_distinct_from_mass() -> None:
    schedule = ParishSchedule(regular=[
        _mass("Sunday", "09:00"),
        _confession("Saturday", "16:00", "18:00"),
    ])
    result = format_schedule(schedule, "en")
    lines = result.splitlines()
    mass_idx = next(i for i, l in enumerate(lines) if "Mass Times" in l)
    conf_idx = next(i for i, l in enumerate(lines) if "Confession" in l and "Mass" not in l)
    assert conf_idx > mass_idx


def test_no_confession_shows_fallback_with_contact_hint() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    result = format_schedule(schedule, "en")
    assert "No Confession" in result
    assert "/contact" in result


def test_no_confession_spanish_fallback() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    result = format_schedule(schedule, "es")
    assert "/contacto" in result


# ---------------------------------------------------------------------------
# Special schedule (S-03)
# ---------------------------------------------------------------------------

def _special(name: str, days_from_today: int, duration: int, entries: list[ScheduleEntry] | None = None) -> SpecialSchedule:
    today = date.today()
    start = today + timedelta(days=days_from_today)
    return SpecialSchedule(
        name=name,
        start_date=start,
        end_date=start + timedelta(days=duration - 1),
        entries=entries or [_mass("Sunday", "10:00")],
    )


def test_active_special_schedule_replaces_regular() -> None:
    regular = [_mass("Sunday", "09:00", Language.EN)]
    special = _special("Holy Week", days_from_today=-1, duration=7)
    schedule = ParishSchedule(regular=regular, special=special)
    result = format_schedule(schedule, "en")
    assert "9 AM" not in result
    assert "10 AM" in result


def test_active_special_schedule_shows_name() -> None:
    special = _special("Holy Week", days_from_today=-1, duration=7)
    schedule = ParishSchedule(regular=[], special=special)
    result = format_schedule(schedule, "en")
    assert "Holy Week" in result


def test_active_special_schedule_shows_date_range() -> None:
    from telegram.schedule import _format_date_range
    today = date.today()
    special = SpecialSchedule(
        name="Holy Week",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=5),
        entries=[_mass("Sunday", "10:00")],
    )
    schedule = ParishSchedule(regular=[], special=special)
    result = format_schedule(schedule, "en")
    assert _format_date_range(special.start_date, special.end_date) in result


def test_upcoming_special_schedule_shown_after_regular() -> None:
    regular = [_mass("Sunday", "09:00")]
    special = _special("Christmas", days_from_today=3, duration=3)
    schedule = ParishSchedule(regular=regular, special=special)
    result = format_schedule(schedule, "en")
    assert "9 AM" in result
    assert "Christmas" in result
    assert result.index("9 AM") < result.index("Christmas")


def test_upcoming_special_schedule_shows_upcoming_label() -> None:
    special = _special("Christmas", days_from_today=3, duration=3)
    schedule = ParishSchedule(regular=[], special=special)
    result = format_schedule(schedule, "en")
    assert "Upcoming" in result


def test_upcoming_special_schedule_spanish_label() -> None:
    special = _special("Navidad", days_from_today=3, duration=3)
    schedule = ParishSchedule(regular=[], special=special)
    result = format_schedule(schedule, "es")
    assert "Próximamente" in result


def test_no_special_schedule_not_mentioned() -> None:
    schedule = ParishSchedule(regular=[_mass("Sunday", "09:00")])
    result = format_schedule(schedule, "en")
    assert "Upcoming" not in result


def test_date_range_same_month() -> None:
    from telegram.schedule import _format_date_range
    start = date(2026, 4, 13)
    end = date(2026, 4, 20)
    assert _format_date_range(start, end) == "Apr 13–20"


def test_date_range_different_months() -> None:
    from telegram.schedule import _format_date_range
    start = date(2025, 12, 24)
    end = date(2026, 1, 6)
    assert _format_date_range(start, end) == "Dec 24 – Jan 6"


# ---------------------------------------------------------------------------
# Error handling (S-04)
# ---------------------------------------------------------------------------

def test_handle_schedules_returns_error_string_on_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock
    adapter = MagicMock()
    adapter.get_schedule.side_effect = ScheduleUnavailableError("unreachable")
    result = handle_schedules(adapter, "en")
    assert "sorry" in result.lower() and "wasn't able" in result.lower()
    assert "/contact" in result


def test_handle_schedules_spanish_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock
    adapter = MagicMock()
    adapter.get_schedule.side_effect = ScheduleUnavailableError("unreachable")
    result = handle_schedules(adapter, "es")
    assert "Lo siento" in result and "horarios" in result
    assert "/contacto" in result
