import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings

from telegram.client import delete_webhook, register_webhook
from telegram.router import router as telegram_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # A shared pool lets every request reuse existing DB connections rather than
    # opening and closing one per query, which would be too slow for KB retrieval.
    app.state.db_pool = await asyncpg.create_pool(settings.database_url)
    # TODO: In production, gracefully handle the case where Telegram is down or the webhook registration fails.
    await register_webhook()
    yield
    await delete_webhook()
    await app.state.db_pool.close()


app = FastAPI(title="Parish Companion", version="0.1.0", lifespan=lifespan)

app.include_router(telegram_router)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
