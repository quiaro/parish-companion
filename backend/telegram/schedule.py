from collections import defaultdict

from schedules.adapter import ScheduleAdapter
from schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType, ScheduleUnavailableError
from translations import get_string

_DAY_INDEX: dict[str, int] = {
    "sunday": 0, "domingo": 0,
    "monday": 1, "lunes": 1,
    "tuesday": 2, "martes": 2,
    "wednesday": 3, "miércoles": 3, "miercoles": 3,
    "thursday": 4, "jueves": 4,
    "friday": 5, "viernes": 5,
    "saturday": 6, "sábado": 6, "sabado": 6,
}

_DAY_NAMES: dict[int, dict[str, str]] = {
    0: {"en": "Sunday",    "es": "Domingo"},
    1: {"en": "Monday",    "es": "Lunes"},
    2: {"en": "Tuesday",   "es": "Martes"},
    3: {"en": "Wednesday", "es": "Miércoles"},
    4: {"en": "Thursday",  "es": "Jueves"},
    5: {"en": "Friday",    "es": "Viernes"},
    6: {"en": "Saturday",  "es": "Sábado"},
}

_LANG_NAMES: dict[str, dict[str, str]] = {
    Language.EN.value: {"en": "English", "es": "inglés"},
    Language.ES.value: {"en": "Spanish", "es": "español"},
}


def handle_schedules(adapter: ScheduleAdapter, language: str) -> str:
    try:
        schedule = adapter.get_schedule()
    except ScheduleUnavailableError:
        return get_string("schedule_unavailable", language)
    return format_schedule(schedule, language)


def format_schedule(schedule: ParishSchedule, language: str) -> str:
    mass = [e for e in schedule.regular if e.type == ScheduleType.MASS]
    confession = [e for e in schedule.regular if e.type == ScheduleType.CONFESSION]

    parts: list[str] = [f"*{get_string('schedule_mass_header', language)}*", ""]

    if mass:
        parts.append(_format_entries_by_day(mass, language))

    parts += ["", f"*{get_string('schedule_confession_header', language)}*", ""]

    if confession:
        parts.append(_format_entries_by_day(confession, language))
    else:
        parts.append(get_string("schedule_no_confession", language))

    return "\n".join(parts)


def _format_entries_by_day(entries: list[ScheduleEntry], language: str) -> str:
    groups: dict[int, list[ScheduleEntry]] = defaultdict(list)
    for entry in entries:
        groups[_DAY_INDEX.get(entry.day.lower(), 99)].append(entry)

    lines = []
    for idx in sorted(groups):
        day_name = _DAY_NAMES.get(idx, {}).get(language, str(idx))
        time_strs = []
        for e in groups[idx]:
            t = _format_time_range(e.start_time, e.end_time)
            if e.language:
                lang = _LANG_NAMES.get(e.language.value, {}).get(language, e.language.value)
                t += f" ({lang})"
            time_strs.append(t)
        lines.append(f"{day_name}: {', '.join(time_strs)}")

    return "\n".join(lines)


def _format_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"


def _format_time_range(start: str, end: str | None) -> str:
    return f"{_format_time(start)}–{_format_time(end)}" if end else _format_time(start)
