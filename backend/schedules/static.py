from schedules.adapter import ScheduleAdapter
from schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType


class StaticScheduleAdapter(ScheduleAdapter):
    """
    Hardcoded schedule for local development and testing.

    Useful for parishes that don't need a spreadsheet, or for contributors
    who want to run the bot without Google credentials.
    """

    def __init__(self, schedule: ParishSchedule | None = None):
        self._schedule = schedule or _default_schedule()

    def get_schedule(self) -> ParishSchedule:
        return self._schedule


def _default_schedule() -> ParishSchedule:
    return ParishSchedule(
        regular=[
            ScheduleEntry(type=ScheduleType.MASS, day="Domingo", start_time="09:00", language=Language.EN),
            ScheduleEntry(type=ScheduleType.MASS, day="Domingo", start_time="11:00", language=Language.ES),
            ScheduleEntry(type=ScheduleType.MASS, day="Sábado", start_time="18:00", language=Language.EN),
            ScheduleEntry(type=ScheduleType.CONFESSION, day="Sábado", start_time="16:00", end_time="18:00"),
        ]
    )
