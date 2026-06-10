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
   | `POSTGRES_PASSWORD`          | Postgres password (any string for local dev)                                |
   | `OPENROUTER_API_KEY`         | Key from [openrouter.ai/keys](https://openrouter.ai/keys)                   |
   | `OPENROUTER_EMBEDDING_MODEL` | Open Router embedding model identifier (e.g. openai/text-embedding-3-small) |
   | `OPENROUTER_CHAT_MODEL`      | Open Router LLM identifier (e.g. anthropic/claude-sonnet-4.6)               |

## Running

```bash
docker compose up --build
```

This starts three services:

| Service    | Host port | Description               |
| ---------- | --------- | ------------------------- |
| `backend`  | 8000      | FastAPI app + Uvicorn     |
| `postgres` | —         | Postgres 16 with pgvector |
| `redis`    | —         | Session cache             |

`postgres` and `redis` are intentionally not exposed to the host in production — the backend reaches them over Docker's internal network. See [Observability (Langfuse)](#observability-langfuse) for the remapped dev ports.

The database schema (tables and vector indexes) is applied automatically on first start via `backend/db/init.sql`.

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

### Picking up DB schema changes

`backend/db/init.sql` is only executed by Postgres on the very first start. If the volume already exists, changes to `init.sql` won't take effect with a normal restart or rebuild.

To apply schema changes, wipe the volume and restart.

**Production:**

```bash
docker compose down -v
docker compose up -d --build
```

**Development:**

```bash
docker compose down -v
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

> **Note:** This deletes all Postgres data.

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
docker compose down          # stop and remove containers
docker compose down -v       # also remove the postgres volume
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

## Running tests

### Backend

Backend tests must be run inside the `dev` stage container, which includes `pytest`. Start the stack with the dev override first:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend
```

Then run the suite:

```bash
docker compose exec backend pytest -v
```

No database or Redis connection is made during the unit tests — the suite uses FastAPI's `TestClient` and stubs out external dependencies via `monkeypatch`.

## Development with VS Code Dev Containers

The repo includes a `.devcontainer` configuration that attaches VS Code directly to the running `backend` container, with Postgres and Redis available as sibling services.

**Prerequisites:** [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and [Container Tools](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-containers) extensions installed.

**Opening the dev container:**

1. Complete the [Setup](#setup) step (`.env` file must exist before the container starts).
2. Open the Command Palette (`Cmd+Shift+P`) and run **Dev Containers: Reopen in Container**.
   VS Code will build the image, start all three services, and attach to the `backend` container.
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

# Postgres (addressed by service name, not localhost)
# IMPORTANT! Remember to replace `pg_user`, `pg_password` and `pg_db` with the values set in the .env file.
python -c "
import asyncpg, asyncio
async def check():
    conn = await asyncpg.connect('postgresql://pg_user:pg_password@postgres:5432/pg_db')
    print(await conn.fetchval('SELECT version()'))
    await conn.close()
asyncio.run(check())
"
```

**Rebuilding after dependency changes:**

After editing `pyproject.toml`, rebuild the container so `uv` picks up the new packages:

```
Cmd+Shift+P → Dev Containers: Rebuild Container
```
