import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config import settings
from commands.contact.email_notifier import EmailContactNotifier
from commands.schedules import CachedScheduleAdapter, GoogleSheetsScheduleAdapter, StaticScheduleAdapter
from telegram.client import check_connectivity, delete_webhook, register_webhook
from telegram.router import router as telegram_router

logging.basicConfig(level=logging.INFO)


def _build_schedule_adapter():
    if settings.schedules_google_credentials_path and settings.schedules_google_spreadsheet_id:
        base = GoogleSheetsScheduleAdapter(
            spreadsheet_id=settings.schedules_google_spreadsheet_id,
            credentials_path=settings.schedules_google_credentials_path,
        )
        return CachedScheduleAdapter(base, ttl_seconds=settings.schedules_cache_ttl_seconds)
    return StaticScheduleAdapter()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    _app.state.schedule_adapter = _build_schedule_adapter()
    _app.state.contact_notifier = EmailContactNotifier()
    await register_webhook()
    yield
    await delete_webhook()


app = FastAPI(title="Parish Companion", version="0.1.0", lifespan=lifespan)

app.include_router(telegram_router)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    # telegram_reachable reflects Telegram's availability: false
    # here means "check your network/VPN," instead of "the app is broken."
    return JSONResponse({"status": "ok", "telegram_reachable": await check_connectivity()})
