import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from schedules.adapter import ScheduleAdapter
from schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType, ScheduleUnavailableError, SpecialSchedule

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_UPCOMING_WINDOW_DAYS = 7
_TYPE_ALIASES: dict[str, str] = {
    "misa": "mass",
    "confesión": "confession",
    "confesion": "confession",
}
_VALID_DAYS: frozenset[str] = frozenset({
    "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "domingo", "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado",
})


class GoogleSheetsScheduleAdapter(ScheduleAdapter):
    """
    Reads Mass and Confession schedules from a Google Spreadsheet.

    Expected sheet layout
    ---------------------
    Tab named by REGULAR_SCHEDULE_TAB  — columns: Type, Day, Time, End Time, Language, Notes
    Tab named by SPECIAL_SCHEDULE_TAB  — columns: Name, Start Date, End Date, Type, Day, Time, End Time, Language, Notes

    Dates in "Special Schedules" must be in ISO 8601 format (YYYY-MM-DD).
    Special schedule rows are denormalised: repeat Name/Start Date/End Date on
    every entry row that belongs to the same schedule.
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

    def get_schedule(self) -> ParishSchedule:
        try:
            client = self._get_client()
            spreadsheet = client.open_by_key(self._spreadsheet_id)
            regular = self._read_regular(spreadsheet)
            special = self._read_special(spreadsheet)
            return ParishSchedule(regular=regular, special=special)
        except Exception as exc:
            raise ScheduleUnavailableError(
                f"Could not retrieve schedule from Google Sheets: {exc}"
            ) from exc

    def _read_regular(self, spreadsheet: gspread.Spreadsheet) -> list[ScheduleEntry]:
        worksheet = spreadsheet.worksheet(settings.regular_schedule_tab)
        rows = worksheet.get_all_records()
        entries = []
        for row_index, row in enumerate(rows, start=2):
            if not (row.get("Type") and row.get("Day") and row.get("Time")):
                continue
            entry = self._parse_entry(row, row_index)
            if entry is not None:
                entries.append(entry)
        return entries

    def _read_special(self, spreadsheet: gspread.Spreadsheet) -> Optional[SpecialSchedule]:
        try:
            worksheet = spreadsheet.worksheet(settings.special_schedule_tab)
        except gspread.WorksheetNotFound:
            return None

        rows = worksheet.get_all_records()
        if not rows:
            return None

        # Group entry rows by (name, start_date, end_date).
        groups: dict[tuple[str, date, date], list[ScheduleEntry]] = defaultdict(list)
        for row_index, row in enumerate(rows, start=2):
            if not (row.get("Name") and row.get("Start Date") and row.get("End Date")):
                continue
            if not (row.get("Type") and row.get("Day") and row.get("Time")):
                continue
            try:
                start = date.fromisoformat(str(row["Start Date"]).strip())
                end = date.fromisoformat(str(row["End Date"]).strip())
            except ValueError:
                logger.warning("Row %d: invalid dates — skipping", row_index)
                continue
            key = (str(row["Name"]).strip(), start, end)
            entry = self._parse_entry(row, row_index)
            if entry is not None:
                groups[key].append(entry)

        return self._pick_relevant_schedule(groups)

    def _parse_entry(self, row: dict, row_index: int = 0) -> Optional[ScheduleEntry]:
        raw_type = str(row.get("Type", "")).strip().lower()
        raw_type = _TYPE_ALIASES.get(raw_type, raw_type)
        try:
            schedule_type = ScheduleType(raw_type)
        except ValueError:
            logger.warning("Row %d: unrecognized type %r — skipping", row_index, raw_type)
            return None
        raw_day = str(row.get("Day", "")).strip()
        if raw_day.lower() not in _VALID_DAYS:
            logger.warning("Row %d: unrecognized day %r — skipping", row_index, raw_day)
            return None
        start_time = self._parse_time(str(row.get("Time", "")).strip(), row_index)
        if start_time is None:
            return None
        raw_end = str(row.get("End Time", "")).strip() if row.get("End Time") else ""
        return ScheduleEntry(
            type=schedule_type,
            day=raw_day,
            start_time=start_time,
            end_time=self._parse_time(raw_end, row_index),
            language=self._parse_language(row.get("Language"), row_index),
            notes=str(row["Notes"]).strip() or None if row.get("Notes") else None,
        )

    @staticmethod
    def _parse_time(raw: str, row_index: int = 0) -> Optional[str]:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%H:%M").strftime("%H:%M")
        except ValueError:
            logger.warning("Row %d: invalid time %r, expected HH:MM — skipping", row_index, raw)
            return None

    def _parse_language(self, raw, row_index: int = 0) -> Optional[Language]:
        if not raw:
            return None
        try:
            return Language(str(raw).strip().lower())
        except ValueError:
            logger.warning("Row %d: unrecognized language code %r — ignoring", row_index, raw)
            return None

    @staticmethod
    def _pick_relevant_schedule(
        groups: dict[tuple[str, date, date], list[ScheduleEntry]],
    ) -> Optional[SpecialSchedule]:
        today = date.today()
        window_end = today + timedelta(days=_UPCOMING_WINDOW_DAYS)

        active: list[SpecialSchedule] = []
        upcoming: list[SpecialSchedule] = []

        for (name, start, end), entries in groups.items():
            schedule = SpecialSchedule(name=name, start_date=start, end_date=end, entries=entries)
            if start <= today <= end:
                active.append(schedule)
            elif today < start <= window_end:
                upcoming.append(schedule)

        if active:
            # If multiple are active, surface the one that started most recently.
            return max(active, key=lambda s: s.start_date)
        if upcoming:
            # Surface the soonest upcoming.
            return min(upcoming, key=lambda s: s.start_date)
        return None
