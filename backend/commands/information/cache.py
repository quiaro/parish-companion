import time
from typing import Optional

from commands.information.adapter import InformationAdapter
from commands.information.models import InformationTopic


class CachedInformationAdapter(InformationAdapter):
    """Wraps any InformationAdapter and caches its topic list for ttl_seconds."""

    def __init__(self, adapter: InformationAdapter, ttl_seconds: int = 3600):
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cached: Optional[list[InformationTopic]] = None
        self._fetched_at: Optional[float] = None

    def list_topics(self) -> list[InformationTopic]:
        now = time.time()
        if self._cached is None or (now - self._fetched_at) > self._ttl:  # type: ignore[operator]
            self._cached = self._adapter.list_topics()
            self._fetched_at = now
        return self._cached

    def get_topic(self, key: str) -> Optional[InformationTopic]:
        return next((t for t in self.list_topics() if t.key == key), None)
