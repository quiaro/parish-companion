from commands.schedules.adapter import ScheduleAdapter
from commands.schedules.cache import CachedScheduleAdapter
from commands.schedules.google_sheets import GoogleSheetsScheduleAdapter
from commands.schedules.models import (
    Language,
    ParishSchedule,
    ScheduleEntry,
    ScheduleType,
    ScheduleUnavailableError,
    SpecialSchedule,
)
from commands.schedules.static import StaticScheduleAdapter
from config import settings

__all__ = [
    "Language",
    "ScheduleAdapter",
    "CachedScheduleAdapter",
    "GoogleSheetsScheduleAdapter",
    "ParishSchedule",
    "ScheduleEntry",
    "ScheduleType",
    "ScheduleUnavailableError",
    "SpecialSchedule",
    "StaticScheduleAdapter",
    "is_configured",
]


def is_configured() -> bool:
    return bool(settings.schedules_google_credentials_path and settings.schedules_google_spreadsheet_id)
