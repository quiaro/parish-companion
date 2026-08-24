from abc import ABC, abstractmethod
from typing import Optional

from commands.information.models import InformationTopic


class InformationAdapter(ABC):

    @abstractmethod
    def list_topics(self) -> list[InformationTopic]:
        """
        Fetch all information topics, sorted by order. Raises
        InformationUnavailableError if data cannot be retrieved.
        """
        pass

    @abstractmethod
    def get_topic(self, key: str) -> Optional[InformationTopic]:
        """
        Fetch a single topic by key, or None if no topic with that key exists.
        Raises InformationUnavailableError if data cannot be retrieved.
        """
        pass
