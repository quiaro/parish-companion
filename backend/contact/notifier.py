from abc import ABC, abstractmethod

from contact.models import ContactRequest


class ContactNotifier(ABC):

    @abstractmethod
    def send(self, request: ContactRequest) -> bool:
        """
        Forward a contact request to parish staff. Returns True on success,
        False on failure — never raises.
        """
