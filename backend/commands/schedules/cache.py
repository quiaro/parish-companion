import time
from typing import Optional

from commands.schedules.adapter import ScheduleAdapter
from commands.schedules.models import ParishSchedule


class CachedScheduleAdapter(ScheduleAdapter):
    """Wraps any ScheduleAdapter and caches its result for ttl_seconds."""

    def __init__(self, adapter: ScheduleAdapter, ttl_seconds: int = 3600):
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cached: Optional[ParishSchedule] = None
        self._fetched_at: Optional[float] = None

    def get_schedule(self) -> ParishSchedule:
        now = time.time()
        if self._cached is None or (now - self._fetched_at) > self._ttl:  # type: ignore[operator]
            self._cached = self._adapter.get_schedule()
            self._fetched_at = now
        return self._cached
