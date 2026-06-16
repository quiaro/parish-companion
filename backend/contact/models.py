from dataclasses import dataclass


@dataclass
class ContactRequest:
    name: str
    contact_info: str
    request_type: str
    message: str
    preferred_contact: str
    preferred_time: str
