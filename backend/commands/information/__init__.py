from commands.information.adapter import InformationAdapter
from commands.information.cache import CachedInformationAdapter
from commands.information.google_sheets import GoogleSheetsInformationAdapter
from commands.information.models import InformationTopic, InformationUnavailableError
from config import settings

__all__ = [
    "CachedInformationAdapter",
    "GoogleSheetsInformationAdapter",
    "InformationAdapter",
    "InformationTopic",
    "InformationUnavailableError",
    "is_configured",
]


def is_configured() -> bool:
    return bool(settings.information_google_credentials_path and settings.information_google_spreadsheet_id)
