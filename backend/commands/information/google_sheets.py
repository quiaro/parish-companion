import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from commands.information.adapter import InformationAdapter
from commands.information.models import InformationTopic, InformationUnavailableError

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class GoogleSheetsInformationAdapter(InformationAdapter):
    """
    Reads parish information topics from a Google Spreadsheet.

    Expected sheet layout
    ----------------------
    Columns in tab named by INFORMATION_TOPICS_TAB: topic_key, label_en, body_en,
    label_es, body_es, order.
    """

    def __init__(self, spreadsheet_id: str, credentials_path: str):
        self._spreadsheet_id = spreadsheet_id
        self._credentials_path = credentials_path
        self._client: Optional[gspread.Client] = None

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            creds = Credentials.from_service_account_file(
                self._credentials_path, scopes=_SCOPES
            )
            self._client = gspread.authorize(creds)
        return self._client

    def list_topics(self) -> list[InformationTopic]:
        try:
            client = self._get_client()
            spreadsheet = client.open_by_key(self._spreadsheet_id)
            worksheet = spreadsheet.worksheet(settings.information_topics_tab)
        except gspread.WorksheetNotFound as exc:
            logger.error(
                "Information tab %r not found — check INFORMATION_TOPICS_TAB for a typo "
                "or a renamed tab: %s",
                settings.information_topics_tab, exc,
            )
            raise InformationUnavailableError(
                f"Information tab {settings.information_topics_tab!r} not found"
            ) from exc
        except Exception as exc:
            logger.error("Could not retrieve information topics from Google Sheets: %s", exc)
            raise InformationUnavailableError(
                f"Could not retrieve information topics from Google Sheets: {exc}"
            ) from exc

        try:
            rows = worksheet.get_all_records()
        except Exception as exc:
            logger.error("Could not read information topics: %s", exc)
            raise InformationUnavailableError(f"Could not read information topics: {exc}") from exc

        topics = []
        for row_index, row in enumerate(rows, start=2):
            topic = self._parse_topic(row, row_index)
            if topic is not None:
                topics.append(topic)

        if not topics:
            logger.warning(
                "Information tab %r has no usable topics — sheet is empty or every "
                "row failed validation",
                settings.information_topics_tab,
            )

        return sorted(topics, key=lambda t: t.order)

    def get_topic(self, key: str) -> Optional[InformationTopic]:
        return next((t for t in self.list_topics() if t.key == key), None)

    def _parse_topic(self, row: dict, row_index: int) -> Optional[InformationTopic]:
        raw_order = row.get("order", "")
        try:
            order = int(str(raw_order).strip())
        except (TypeError, ValueError):
            logger.warning("Row %d: invalid or missing order %r — skipping", row_index, raw_order)
            return None
        try:
            return InformationTopic(
                key=str(row.get("topic_key", "")).strip(),
                label_en=str(row.get("label_en", "")).strip(),
                label_es=str(row.get("label_es", "")).strip(),
                body_en=str(row.get("body_en", "")).strip(),
                body_es=str(row.get("body_es", "")).strip(),
                order=order,
            )
        except ValueError as exc:
            logger.warning("Row %d: %s — skipping", row_index, exc)
            return None
