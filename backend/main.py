import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config import settings
from commands.schedules import CachedScheduleAdapter, GoogleSheetsScheduleAdapter, StaticScheduleAdapter
from telegram.client import delete_webhook, register_webhook
from telegram.router import router as telegram_router

logging.basicConfig(level=logging.INFO)


def _build_schedule_adapter():
    if settings.google_credentials_path and settings.google_spreadsheet_id:
        base = GoogleSheetsScheduleAdapter(
            spreadsheet_id=settings.google_spreadsheet_id,
            credentials_path=settings.google_credentials_path,
        )
        return CachedScheduleAdapter(base, ttl_seconds=settings.cached_schedule_ttl)
    return StaticScheduleAdapter()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    _app.state.schedule_adapter = _build_schedule_adapter()
    # TODO: In production, gracefully handle the case where Telegram is down or the webhook registration fails.
    await register_webhook()
    yield
    await delete_webhook()


app = FastAPI(title="Parish Companion", version="0.1.0", lifespan=lifespan)

app.include_router(telegram_router)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
