# Parish Companion — Claude Instructions

## Documentation structure

| File | Audience | Contents |
| ---- | -------- | -------- |
| `README.md` | Anyone | Mission, vision, principles, privacy, and a Contributing section pointing to the right place. Pure overview — nothing operational. |
| `DEPLOYMENT.md` | Parish adopters | Everything a parish needs to go live: spreadsheet setup, CSV templates, configuration reference, and how to wire in a custom data source. |
| `DEVELOPMENT.md` | Contributors | Everything needed to work on the project: Docker setup, running tests, DevContainers, viewing logs. No deployment or adapter content. |
| `docs/templates/` | Parish adopters | CSV templates for the Regular Schedule and Special Schedules spreadsheet tabs. |

When deciding where to add or update documentation, use the audience column to pick the right file.

## Repository layout

```
backend/
  schedules/      Data layer — ScheduleAdapter interface, models, GoogleSheetsScheduleAdapter, CachedScheduleAdapter, StaticScheduleAdapter
  telegram/       Presentation layer — webhook router, command handlers, schedule formatter, message splitting
  tests/
    commands/     Telegram command integration tests — one file per command (test_static.py, test_schedule.py, …)
  translations.py All user-facing strings (English and Spanish)
  main.py         App entry point; wires the schedule adapter and registers the Telegram webhook
```

## Conventions

**Translations** — All user-facing strings live in `translations.py`. When adding a new string, add it in both `en` and `es` at the same time. `tests/test_translations.py` enforces that both languages always have identical key sets.

**Telegram command tests** — Integration tests for Telegram commands go in `tests/commands/`, one file per command. Keep `test_static.py` for commands whose replies are static strings from `translations.py`, and create a new file for each command whose reply requires a handler or external data.

**Language forcing** — Telegram commands that are inherently in one language (e.g. `/schedules` → English, `/horarios` → Spanish) override the session language in the router. The mapping lives in `_SCHEDULE_COMMAND_LANGUAGES` in `telegram/router.py`. Do not use the session language for these commands.
