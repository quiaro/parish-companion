from dataclasses import dataclass


@dataclass(kw_only=True)
class InformationTopic:
    key: str
    label_en: str
    body_en: str
    label_es: str = ""
    body_es: str = ""
    order: int

    def __post_init__(self) -> None:
        for field_name in ("key", "label_en", "body_en"):
            if not getattr(self, field_name):
                raise ValueError(f"InformationTopic.{field_name} must be non-empty")


class InformationUnavailableError(Exception):
    """Raised when the information data source cannot be reached or parsed."""
    pass
