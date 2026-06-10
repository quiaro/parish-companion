FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
COPY backend/ .

# --- development stage (includes pytest) ------------------------------------
FROM base AS dev
RUN uv pip install --system --no-cache -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- production stage (no dev dependencies) ---------------------------------
FROM base AS production
RUN uv pip install --system --no-cache -e .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
