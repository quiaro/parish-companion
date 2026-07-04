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

| Column   | Required | Description                                |
| -------- | -------- | ------------------------------------------ |
| Type     | Yes      | `mass` or `confession`                     |
| Day      | Yes      | Day of the week, e.g. `Sunday`             |
| Time     | Yes      | Start time in `HH:MM` format, e.g. `09:00` |
| End Time | No       | End time in `HH:MM` format                 |
| Language | No       | BCP 47 language code: `en` or `es`         |
| Notes    | No       | Any additional information                 |

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

## Contact requests

The `/contact` command (and its Spanish equivalent `/contacto`) lets a parishioner reach a member of your parish staff directly through the bot.

### What parishioners experience

1. They type `/contact` or `/contacto`.
2. The bot asks four questions, one at a time:
   - Their name
   - The type of assistance they need (from a list you configure)
   - A brief description of their request
   - The best time to reach them
3. The bot displays a summary of their answers and asks them to confirm.
4. They reply **Yes** (or **Sí**) to send, or **No** to cancel.
5. On confirmation, the bot sends an email to your staff and tells the parishioner that someone will be in touch.

At any point they can type `/cancel` to abandon the request.

### What the staff email looks like

The subject line identifies the request type so staff can route it at a glance:

```
Subject: Parish Companion: Speak with a priest
```

The body includes all the information collected:

```
A parishioner has submitted a contact request through Parish Companion.

Request type: Speak with a priest
Name: Jane Smith
Telegram contact: @janesmith (ID: 111222333)
Message:
I would like to schedule a time to speak with a priest about my upcoming marriage.

Best time to reach: Weekday evenings
```

### Configuration

#### Email delivery

| Variable                   | Default                         | Description                                                       |
| -------------------------- | ------------------------------- | ----------------------------------------------------------------- |
| `CONTACT_EMAIL_RECIPIENTS` | _(required)_                    | JSON array of staff email addresses, e.g. `["pastor@parish.org"]` |
| `SMTP_HOST`                | _(required)_                    | SMTP server hostname, e.g. `smtp.gmail.com`                       |
| `SMTP_PORT`                | `587`                           | SMTP server port                                                  |
| `SMTP_USERNAME`            | _(none)_                        | SMTP username (usually your full email address)                   |
| `SMTP_PASSWORD`            | _(none)_                        | SMTP password or app password                                     |
| `SMTP_USE_TLS`             | `true`                          | Set to `false` only if your mail server does not support STARTTLS |
| `SMTP_FROM_ADDRESS`        | _(falls back to SMTP_USERNAME)_ | The sender address shown on outgoing emails                       |

**Gmail users:** Generate an [App Password](https://support.google.com/accounts/answer/185833) rather than using your account password. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, and `SMTP_USE_TLS=true`.

#### Request type options

| Variable                   | Default                                                                                              | Description                                                 |
| -------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `CONTACT_REQUEST_TYPES`    | `["Speak with a priest", "Spiritual director appointment", "Pastoral minister", "General question"]` | Options shown to English-speaking parishioners (JSON array) |
| `CONTACT_REQUEST_TYPES_ES` | _(falls back to English list)_                                                                       | Options shown to Spanish-speaking parishioners (JSON array) |

The selected type appears in the email subject line, so staff can see immediately who should handle the request. To change the options, update the environment variable — no code change is required.

Example Spanish list to match the default English options:

```
CONTACT_REQUEST_TYPES_ES=["Hablar con un sacerdote", "Cita con director espiritual", "Ministro pastoral", "Pregunta general"]
```

#### Fallback contact

| Variable        | Default  | Description                                                                                     |
| --------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `CONTACT_PHONE` | _(none)_ | Parish phone number. If set, shown to parishioners in the rare event that email delivery fails. |

## Database & backups

Parish Companion stores per-parishioner state (used by features like `/comfort`) in Postgres, which runs as part of the Docker Compose stack alongside the bot and Redis.

### Backups

A dedicated `backup` service runs `pg_dump` once daily and uploads the result to an Amazon S3 Standard bucket, naming the file after the day of the week (`backup-monday.sql`, `backup-tuesday.sql`, ...). Each new backup overwrites that same weekday's file from the previous week, giving a **rolling one-week history of 7 files**.

**Recovery window tradeoff, chosen deliberately:** you can restore to any of the past 7 days (whichever weekday's backup predates the issue), but not further back than one week, and not to a granularity finer than once per day. This is an accepted tradeoff for the project's current stage — revisit (longer retention, multiple snapshots per day) if this stops being acceptable once real usage exists.

### Restore procedure

1. Download the desired weekday's backup from S3:

   ```bash
   aws s3 cp s3://$BACKUP_S3_BUCKET/backup-monday.sql ./restore.sql
   ```

2. Stop the backend so nothing writes to Postgres during the restore:

   ```bash
   docker compose stop backend
   ```

3. Restore into the running Postgres instance (this expects a fresh/empty database — if restoring after data corruption, drop and recreate the database first):

   ```bash
   docker compose exec -T postgres psql -U $POSTGRES_USER -d $POSTGRES_DB < restore.sql
   ```

4. Restart the backend:

   ```bash
   docker compose start backend
   ```

### Configuration

| Variable                | Default       | Description                                                          |
| ------------------------ | ------------- | ---------------------------------------------------------------------- |
| `POSTGRES_USER`          | _(required)_  | Postgres username                                                       |
| `POSTGRES_PASSWORD`      | _(required)_  | Postgres password                                                       |
| `POSTGRES_DB`             | _(required)_  | Postgres database name                                                  |
| `DATABASE_URL`            | _(required)_  | SQLAlchemy connection string, e.g. `postgresql+psycopg://user:pass@postgres:5432/db` |
| `AWS_ACCESS_KEY_ID`       | _(required)_  | AWS credential used to upload backups to S3                            |
| `AWS_SECRET_ACCESS_KEY`   | _(required)_  | AWS credential used to upload backups to S3                            |
| `AWS_DEFAULT_REGION`      | _(required)_  | AWS region of the backup bucket                                         |
| `BACKUP_S3_BUCKET`        | _(required)_  | Name of the S3 Standard bucket backups are uploaded to                 |

Postgres is not exposed on a public port — it's only reachable from the bot's and backup job's containers, over Docker's internal network.

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
