# Parish Companion

## Features

- **Telegram support** — handles customer messages over Telegram
- **Multilingual** — detects the customer's language from their message and responds in kind; currently supports English and Spanish

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (`docker compose version`)

## Setup

1. Copy the environment file and fill in your credentials:

   ```bash
   cp .env.example .env
   ```

   Required values to set in `.env`:

   | Variable                     | Description                                                                 |
   | ---------------------------- | --------------------------------------------------------------------------- |
   | `TELEGRAM_BOT_TOKEN`         | Token from [@BotFather](https://t.me/botfather)                             |
   | `TELEGRAM_WEBHOOK_SECRET`    | Random string used to authenticate Telegram's POST requests                 |
   | `OPENROUTER_API_KEY`         | Key from [openrouter.ai/keys](https://openrouter.ai/keys)                   |
   | `OPENROUTER_EMBEDDING_MODEL` | Open Router embedding model identifier (e.g. openai/text-embedding-3-small) |
   | `OPENROUTER_CHAT_MODEL`      | Open Router LLM identifier (e.g. anthropic/claude-sonnet-4.6)               |

## Running

```bash
docker compose up --build
```

This starts:

| Service    | Host port | Description                                        |
| ---------- | --------- | -------------------------------------------------- |
| `backend`  | 8000      | FastAPI app + Uvicorn                              |
| `redis`    | —         | Session cache                                      |
| `postgres` | —         | Per-parishioner persistent state (e.g. `/comfort`) |
| `qdrant`   | —         | Bible verse-bank vector store                      |
| `backup`   | —         | Daily `pg_dump` → S3 (production only, see below)  |

`redis`, `postgres`, and `qdrant` are intentionally not exposed to the host in production — the backend reaches them over Docker's internal network. `docker-compose.dev.yml` remaps all three to host ports (`6380`, `5433`, and `6333` respectively) so a local client can be connected while developing.

**`backup` doesn't start in local dev.** It's assigned a profile (`production-only`) in `docker-compose.dev.yml` that's never activated by the documented dev command, so it's excluded whenever you use the dev override — no AWS credentials are needed just to run the stack locally. Running `docker compose up --build` with the base file alone (i.e. without `-f docker-compose.dev.yml`) still starts it normally, which is what production deployments do.

Verify everything is up:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Picking up Python source changes

Python source files are baked into the image at build time, so editing them requires a rebuild.

**Production:**

```bash
docker compose up -d --build backend
```

**Development (includes `pytest`):**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend
```

- **`-d`** — runs the container in the background (detached), returning you to the shell prompt immediately.
- **`--build`** — rebuilds the `backend` image before starting the container, picking up any changes to `.py` files, `Dockerfile`, or `pyproject.toml`.

> **Note:** `postgres` and `redis` services use pre-built images from Docker Hub so, since there are no local source files baked into them, they don't need to be rebuilt.

### Picking up `.env` changes

Making any changes to the `.env` file will require a forced recreation of the affected service.

**Production:**

```bash
docker compose up -d --force-recreate backend
```

**Development:**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate backend
```

- **`-d`** — runs the container in the background (detached), returning you to the shell prompt immediately.
- **`--force-recreate`** — tears down and recreates the container ensuring the new env vars are loaded.

### Stopping

```bash
docker compose down
```

## Connecting to Telegram

The bot receives messages via a webhook — Telegram POSTs every incoming update to `/webhook` on a publicly reachable HTTPS URL. For local development, [ngrok](https://ngrok.com) creates that public URL and tunnels traffic to your machine.

**Prerequisites:** [Install ngrok](https://ngrok.com/download) on your host machine (not inside the container).

**Steps:**

1. Start the stack first (`docker compose up --build`), so port 8000 is available on the host.

2. In a separate terminal, start ngrok:

   ```bash
   ngrok http 8000
   ```

   ngrok prints a forwarding URL like `https://abc123.ngrok-free.app`. Copy it.

3. Set `TELEGRAM_WEBHOOK_URL` in `.env`:

   ```
   TELEGRAM_WEBHOOK_URL=https://abc123.ngrok-free.app/webhook
   ```

4. Recreate the backend container so it picks up the new value and registers the webhook on startup:

   ```bash
   docker compose up -d --force-recreate backend
   ```

   You should see `Webhook registered: https://abc123.ngrok-free.app/webhook` in the logs.

5. Open Telegram, find your bot by username, and send it a message. The full request flow will be visible in `docker compose logs -f backend`.

> **Note:** The ngrok URL changes every time you restart ngrok (on the free plan). When that happens, update `TELEGRAM_WEBHOOK_URL` in `.env` and recreate the backend container again.
>
> For local `curl` testing without ngrok, leave `TELEGRAM_WEBHOOK_URL` unset — the backend starts normally and skips webhook registration.

## Viewing logs

Application logs are written to stdout and captured by Docker.

Stream logs live while testing:

```bash
docker compose logs -f backend
```

See all logs since startup:

```bash
docker compose logs backend
```

Uvicorn access log lines appear at `INFO` level; application errors (from `logger.error(...)` calls) appear at `ERROR` level.

## Docker build stages

The backend `Dockerfile` defines two stages:

| Stage        | Command                                                                     | Description                                                                         |
| ------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `production` | `docker compose up --build`                                                 | App dependencies only. Used by default.                                             |
| `dev`        | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build` | Adds `pytest` and `pytest-asyncio` for running the test suite inside the container. |

The `docker-compose.dev.yml` override file sets `target: dev`, replacing the `production` target for that run without modifying `docker-compose.yml`.

## Database migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/). There's no auto-migrate-on-boot step — this project's convention is explicit, manual commands for anything that changes running state (see the `--force-recreate` steps above), and migrations follow the same pattern.

After starting the stack, apply migrations by running:

```bash
docker compose exec backend alembic upgrade head
```

Run this once after first bringing up the stack, and again after pulling any update that adds a new file under `backend/alembic/versions/`.

To add a new migration, create a new revision file under `backend/alembic/versions/` (see the existing ones for the pattern — hand-written to match the target schema exactly, rather than relying on autogenerate) and apply it the same way.

### Querying the database

**From inside the container** (no local tools needed):

```bash
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
```

**From the host**, with a local `psql` install or a GUI client (TablePlus, DBeaver, pgAdmin, etc.): the dev override remaps Postgres to `localhost:5433`, so connect with:

```bash
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5433/$POSTGRES_DB"
```

This only works when the stack is up via the dev override (`docker compose -f docker-compose.yml -f docker-compose.dev.yml up ...`) — the base production compose file doesn't expose the port to the host at all.

## Bible verse bank ingestion (`/comfort`)

The `/comfort` command retrieves Bible verses from Qdrant, populated from `data/bible_OEB_verses.csv`. This is a manual, occasional operation — not something that runs on every backend startup — so re-run it whenever the CSV changes:

```bash
docker compose exec backend python -m scripts.ingest_verses
```

The script is idempotent: point IDs are derived deterministically from each verse's `reference`, so re-running after editing a few rows updates just those points rather than duplicating the whole collection. Pass a different path as an argument to ingest a different CSV file.

## Running tests

### Backend

Backend tests must be run inside the `dev` stage container, which includes `pytest`. Start the stack with the dev override first:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend
```

This also brings up `postgres` and `redis` as dependencies. Apply migrations before running the suite (see [Database migrations](#database-migrations) above) — the tests under `tests/db/` expect the schema to already exist:

```bash
docker compose exec backend alembic upgrade head
```

Then run the suite:

```bash
docker compose exec backend pytest -v
```

Most of the suite makes no external connections (Redis, Postgres, etc.) — it uses FastAPI's `TestClient` and stubs out external dependencies via `monkeypatch`. The one exception is `tests/db/`, which talks to the real `postgres` sibling service to exercise behavior (`ON CONFLICT` idempotency under concurrent writes, rolling-window timestamp boundaries) that can't be meaningfully faked. Those tests truncate the relevant tables before each test, so they're safe to re-run but will clear out any data you'd put in your local dev database.

## Development with VS Code Dev Containers

The repo includes a `.devcontainer` configuration that attaches VS Code directly to the running `backend` container, with Postgres and Redis available as sibling services.

**Prerequisites:** [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and [Container Tools](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-containers) extensions installed.

**Opening the dev container:**

1. Complete the [Setup](#setup) step (`.env` file must exist before the container starts).
2. Open the Command Palette (`Cmd+Shift+P`) and run **Dev Containers: Reopen in Container**.
   VS Code will build the image, start all services, and attach to the `backend` container.
3. Port 8000 is forwarded automatically — you'll get a notification when it's ready.

**What's included in the container:**

- Python 3.12 interpreter at `/usr/local/bin/python`
- All dependencies installed via `uv` from `backend/pyproject.toml`
- Extensions: Python, Pylance, Ruff (format on save), Docker, Container Tools, TOML support

**Verifying services from the container terminal:**

Since `curl` is not available in the slim Python image, use the installed Python packages instead.

```bash
# Backend
python -c "import httpx; r = httpx.get('http://localhost:8000/health'); print(r.status_code, r.text)"

# Redis (addressed by service name, not localhost)
python -c "import redis; r = redis.from_url('redis://redis:6379'); print(r.ping())"
```

**Rebuilding after dependency changes:**

After editing `pyproject.toml`, rebuild the container so `uv` picks up the new packages:

```
Cmd+Shift+P → Dev Containers: Rebuild Container
```
