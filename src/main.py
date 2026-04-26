"""Główna aplikacja FastAPI."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .database import init_db
from .routes import router
from .worker import WebhookWorker, get_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management aplikacji."""
    # Startup
    await init_db()
    logger.info("Database initialized")

    # Uruchom workera w tle
    worker = await get_worker()
    if settings.worker_enabled:
        asyncio.create_task(worker.start())
        logger.info("Worker started")

    yield

    # Shutdown
    if settings.worker_enabled:
        await worker.stop()
        logger.info("Worker stopped")


app = FastAPI(
    title="Webhook Delivery System",
    description="Reliable webhook delivery microservice",
    version="1.0.0",
    lifespan=lifespan,
)

# Rejestracja routera
app.include_router(router)


# Import loggera na końcu
import logging

logger = logging.getLogger(__name__)