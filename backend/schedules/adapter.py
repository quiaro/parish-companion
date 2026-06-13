from abc import ABC, abstractmethod

from schedules.models import ParishSchedule


class ScheduleAdapter(ABC):

    @abstractmethod
    def get_schedule(self) -> ParishSchedule:
        """
        Fetch the full schedule — regular entries and any active or upcoming
        special schedule. Raises ScheduleUnavailableError if data cannot be
        retrieved.
        """
        pass
