# Parish Companion

**Parish Companion** is an open-source Telegram bot designed to help people grow as disciples of Jesus Christ, and participate more fully in the life and mission of their local parish.

The project is based on a simple idea:

> Technology should not replace the Church, but it can help people encounter Christ, receive encouragement, access spiritual resources, and connect with the human ministries of the Church.

Parish Companion acts as a digital companion that helps users engage with Scripture, prayer, testimony, service, and parish life while encouraging meaningful connections with priests, spiritual counselors, and fellow believers.

## Mission

The mission of Parish Companion is to support the work of local parishes by:

- Encouraging daily reflection on Scripture.
- Inspiring concrete acts of Christian discipleship.
- Helping people recognize God's presence in their lives.
- Facilitating spiritual accompaniment and pastoral care.
- Making parish resources and services more accessible.
- Strengthening the faith community through testimony, prayer, and service.

## Core Principles

### Christ-Centered

The purpose of the bot is to point people toward Jesus Christ and deeper participation in the life of the Church.

### Human-Centered

Whenever possible, the bot encourages users to connect with real people, including priests, spiritual counselors, parish staff, prayer groups, and fellow parishioners.

### Pastoral

The bot seeks to encourage, support, and accompany users with compassion and respect.

### Faithful

The project aims to operate in accordance with Scripture and the teachings of the Church.

### Practical

Spiritual growth is not only about learning. It is also about action, service, prayer, and participation in Christian community.

## Vision

Help more people encounter Christ, participate in parish life, and become active disciples who love God and love their neighbors.

Parish Companion seeks to use technology in service of the Gospel by helping people:

- Encounter God through Scripture and prayer.
- Grow in faith and discipleship.
- Receive encouragement during difficult times.
- Connect with the life of the Church.
- Serve others with love.
- Share the hope they have found in Christ.

## What Parish Companion Is Not

Parish Companion is NOT:

- A replacement for Scripture study.
- A replacement for spiritual direction.
- A replacement for pastoral care.
- A replacement for the sacraments.
- A replacement for Christian community.

The bot exists to help people access and engage with these realities more easily.

## Privacy

Users should never be required to disclose sensitive personal information in order to benefit from the bot.

Parishes deploying Parish Companion should establish clear policies regarding:

- Data retention
- Privacy
- Testimony sharing
- Prayer requests
- Appointment scheduling
- Human follow-up procedures

## Schedule Data

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

## Contributing

Contributions are welcome.

We encourage developers, pastors, theologians, ministry leaders, and parish volunteers to collaborate in improving the project while remaining faithful to its mission.
