from dataclasses import dataclass, field


@dataclass
class ContactRequest:
    name: str
    request_type: str
    message: str
    preferred_time: str
    telegram_user_id: int
    telegram_username: str | None = field(default=None)
    language: str = field(default="en")
