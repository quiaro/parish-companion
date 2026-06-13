import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from schedules.adapter import ScheduleAdapter
from schedules.models import Language, ParishSchedule, ScheduleEntry, ScheduleType, ScheduleUnavailableError, SpecialSchedule

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_UPCOMING_WINDOW_DAYS = 7


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
        for row in rows:
            if not (row.get("Type") and row.get("Day") and row.get("Time")):
                continue
            entry = self._parse_entry(row)
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
        for row in rows:
            if not (row.get("Name") and row.get("Start Date") and row.get("End Date")):
                continue
            if not (row.get("Type") and row.get("Day") and row.get("Time")):
                continue
            try:
                start = date.fromisoformat(str(row["Start Date"]).strip())
                end = date.fromisoformat(str(row["End Date"]).strip())
            except ValueError:
                logger.warning("Skipping special schedule row with unparseable dates: %s", row)
                continue
            key = (str(row["Name"]).strip(), start, end)
            entry = self._parse_entry(row)
            if entry is not None:
                groups[key].append(entry)

        return self._pick_relevant_schedule(groups)

    def _parse_entry(self, row: dict) -> Optional[ScheduleEntry]:
        raw_type = str(row.get("Type", "")).strip().lower()
        try:
            schedule_type = ScheduleType(raw_type)
        except ValueError:
            logger.warning("Skipping row with unrecognized type %r: %s", raw_type, row)
            return None
        return ScheduleEntry(
            type=schedule_type,
            day=str(row["Day"]).strip(),
            start_time=str(row["Time"]).strip(),
            end_time=str(row["End Time"]).strip() or None if row.get("End Time") else None,
            language=self._parse_language(row.get("Language")),
            notes=str(row["Notes"]).strip() or None if row.get("Notes") else None,
        )

    def _parse_language(self, raw) -> Optional[Language]:
        if not raw:
            return None
        try:
            return Language(str(raw).strip().lower())
        except ValueError:
            logger.warning("Unrecognized language code %r, ignoring", raw)
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
