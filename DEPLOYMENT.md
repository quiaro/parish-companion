# Deploying Parish Companion

This guide is for parishes and developers who want to deploy Parish Companion for their own community. It covers how to connect your schedule data and how to configure the bot for your parish.

For information on contributing to the project itself, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Schedule data

Parish Companion reads Mass and Confession times from a Google Spreadsheet. Parish administrators can update the spreadsheet directly — no code changes or developer involvement required. Changes are reflected in the bot within the cache window (see [Configuration](#configuration) below).

In the absence of a Google Spreadsheet, the app falls back to using a static schedule.

### Spreadsheet structure

The spreadsheet must contain two tabs. Their names are configurable via environment variables (see below); the defaults are shown here.

#### Regular Schedule

Tab name: `REGULAR_SCHEDULE_TAB` (default: `Regular Schedule`)

| Column   | Required | Description                                 |
| -------- | -------- | ------------------------------------------- |
| Type     | Yes      | `mass` or `confession`                      |
| Day      | Yes      | Day of the week, e.g. `Sunday`              |
| Time     | Yes      | Start time in `HH:MM` format, e.g. `09:00` |
| End Time | No       | End time in `HH:MM` format                  |
| Language | No       | BCP 47 language code: `en` or `es`          |
| Notes    | No       | Any additional information                  |

Example:

| Type       | Day      | Time  | End Time | Language | Notes |
| ---------- | -------- | ----- | -------- | -------- | ----- |
| mass       | Sunday   | 09:00 |          | en       |       |
| mass       | Sunday   | 11:00 |          | es       |       |
| confession | Saturday | 16:00 | 18:00    |          |       |

#### Special Schedules

Tab name: `SPECIAL_SCHEDULE_TAB` (default: `Special Schedules`)

Used for seasonal or one-off schedule changes such as Holy Week or Christmas.

| Column     | Required | Description                        |
| ---------- | -------- | ---------------------------------- |
| Name       | Yes      | Schedule name, e.g. `Holy Week`    |
| Start Date | Yes      | ISO 8601 date: `YYYY-MM-DD`        |
| End Date   | Yes      | ISO 8601 date: `YYYY-MM-DD`        |
| Type       | Yes      | `mass` or `confession`             |
| Day        | Yes      | Day of the week or specific date   |
| Time       | Yes      | Start time in `HH:MM` format       |
| End Time   | No       | End time in `HH:MM` format         |
| Language   | No       | BCP 47 language code: `en` or `es` |
| Notes      | No       | Any additional information         |

Each special schedule entry is its own row. Repeat the Name, Start Date, and End Date on every row that belongs to the same schedule.

Example:

| Name      | Start Date | End Date   | Type       | Day    | Time  | End Time | Language | Notes |
| --------- | ---------- | ---------- | ---------- | ------ | ----- | -------- | -------- | ----- |
| Holy Week | 2026-03-29 | 2026-04-05 | mass       | Sunday | 08:00 |          |          |       |
| Holy Week | 2026-03-29 | 2026-04-05 | mass       | Sunday | 10:00 |          | es       |       |
| Holy Week | 2026-03-29 | 2026-04-05 | confession | Friday | 17:00 | 19:00    |          |       |

### Setting up the spreadsheet

CSV templates for both tabs are provided in [`docs/templates/`](docs/templates/). To use them:

1. Create a new Google Spreadsheet.
2. For each template file, go to **File → Import**, upload the CSV, and choose **Insert new sheet** — this creates a tab with the correct column headers and example rows already filled in.
3. Rename each tab to match your `REGULAR_SCHEDULE_TAB` and `SPECIAL_SCHEDULE_TAB` settings (defaults: `Regular Schedule` and `Special Schedules`).
4. Replace the example rows with your parish's actual schedule.

The `Type` column accepts values in English (`mass`, `confession`) or Spanish (`misa`, `confesión`).

### Special schedule behavior

When a parishioner requests the schedule:

- If a special schedule is **currently active** (today falls within its date range), the bot presents it instead of the regular schedule.
- If no special schedule is active but one **starts within the next 7 days**, the bot surfaces it alongside the regular schedule as an upcoming notice.
- Once the special schedule period ends, the bot automatically reverts to the regular schedule.

If more than one special schedule is active at the same time, the one that started most recently takes precedence.

### Configuration

| Variable                       | Default                                 | Description                                       |
| ------------------------------ | --------------------------------------- | ------------------------------------------------- |
| `GOOGLE_SPREADSHEET_ID`        | _(required)_                            | The ID from the spreadsheet URL                   |
| `GOOGLE_CREDENTIALS_HOST_PATH` | `./secrets/google-service-account.json` | Path to the service account JSON file on the host |
| `REGULAR_SCHEDULE_TAB`         | `Regular Schedule`                      | Name of the regular schedule tab                  |
| `SPECIAL_SCHEDULE_TAB`         | `Special Schedules`                     | Name of the special schedules tab                 |
| `CACHED_SCHEDULE_TTL`          | `3600`                                  | How long (in seconds) to cache schedule data      |

Schedule data is cached for `CACHED_SCHEDULE_TTL` seconds (default: 1 hour). Updates made to the spreadsheet will be visible to users within that window without any restart required.

## Custom schedule data sources

The schedule feature is built around a `ScheduleAdapter` interface defined in [`backend/schedules/adapter.py`](backend/schedules/adapter.py). The Google Sheets integration is one concrete implementation; you can replace it with any data source — a parish website scraper, a local database, a different spreadsheet tool — without touching bot logic.

### The interface

```python
class ScheduleAdapter(ABC):
    @abstractmethod
    def get_schedule(self) -> ParishSchedule:
        ...
```

`get_schedule` must return a `ParishSchedule` containing:

- `regular` — a list of `ScheduleEntry` objects (Mass and Confession times that repeat weekly)
- `special` — an optional `SpecialSchedule` for seasonal overrides (Holy Week, Christmas, etc.)

Raise `ScheduleUnavailableError` if the data source cannot be reached or the response cannot be parsed. The bot catches this and shows a user-friendly fallback message.

### Minimal example

```python
from schedules.adapter import ScheduleAdapter
from schedules.models import ParishSchedule, ScheduleEntry, ScheduleType

class MyParishAdapter(ScheduleAdapter):
    def get_schedule(self) -> ParishSchedule:
        # fetch from wherever your data lives
        return ParishSchedule(
            regular=[
                ScheduleEntry(type=ScheduleType.MASS, day="Sunday", start_time="09:00"),
            ]
        )
```

### Wiring in your adapter

The active adapter is constructed in `_build_schedule_adapter()` in [`backend/main.py`](backend/main.py). Edit that function to instantiate your adapter, then wrap it with `CachedScheduleAdapter` if you want caching:

```python
from schedules.cache import CachedScheduleAdapter
from my_parish.adapter import MyParishAdapter

def _build_schedule_adapter():
    return CachedScheduleAdapter(MyParishAdapter(), ttl_seconds=3600)
```

No other changes are required. The router, formatter, and all bot logic remain untouched.
