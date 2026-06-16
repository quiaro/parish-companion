from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class ScheduleType(Enum):
    MASS = "mass"
    CONFESSION = "confession"


class Language(Enum):
    EN = "en"
    ES = "es"


@dataclass
class ScheduleEntry:
    type: ScheduleType
    day: str                         # e.g. "Sunday", or ISO date for special schedules
    start_time: str                  # e.g. "09:00"
    end_time: Optional[str] = None   # e.g. "10:00"
    language: Optional[Language] = None
    notes: Optional[str] = None


@dataclass
class SpecialSchedule:
    name: str
    start_date: date
    end_date: date
    entries: list[ScheduleEntry] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.start_date <= date.today() <= self.end_date


@dataclass
class ParishSchedule:
    regular: list[ScheduleEntry] = field(default_factory=list)
    special: Optional[SpecialSchedule] = None


class ScheduleUnavailableError(Exception):
    """Raised when the schedule data source cannot be reached or parsed."""
    pass
