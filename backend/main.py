import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from telegram.client import delete_webhook, register_webhook
from telegram.router import router as telegram_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # TODO: In production, gracefully handle the case where Telegram is down or the webhook registration fails.
    await register_webhook()
    yield
    await delete_webhook()


app = FastAPI(title="Parish Companion", version="0.1.0", lifespan=lifespan)

app.include_router(telegram_router)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
