"""Worker do wysyłania webhooków."""
import asyncio
import logging
from datetime import datetime

import aiohttp
from sqlalchemy import select

from .config import settings
from .database import async_session_factory
from .models import OperationStatus, Webhook, WebhookStatus
from .service import WebhookService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebhookWorker:
    """Worker do wysyłania webhooków w tle."""

    def __init__(self):
        self._running = False
        self._semaphore = asyncio.Semaphore(settings.worker_concurrency)
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Uruchamia workera."""
        self._running = True
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
        )
        logger.info("Webhook worker started")

        while self._running:
            try:
                await self._process_pending_webhooks()
            except Exception as e:
                logger.error(f"Worker error: {e}")

            await asyncio.sleep(1)  # Krótka przerwa między iteracjami

    async def stop(self) -> None:
        """Zatrzymuje workera."""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Webhook worker stopped")

    async def _process_pending_webhooks(self) -> None:
        """Przetwarza oczekujące webhooki."""
        async with async_session_factory() as db:
            service = WebhookService(db)
            pending_webhooks = await service.get_pending_webhooks(limit=50)

            for webhook in pending_webhooks:
                asyncio.create_task(self._deliver_webhook(webhook.id))

    async def _deliver_webhook(self, webhook_id: str) -> None:
        """Dostarcza pojedynczy webhook z obsługą retry."""
        async with self._semaphore:  # Ograniczenie jednoczesnych połączeń
            async with async_session_factory() as db:
                service = WebhookService(db)
                webhook = await service.get_webhook(webhook_id)

                if not webhook or webhook.status != WebhookStatus.PENDING:
                    return

                # Ustaw status na processing
                await service.update_webhook_status(webhook_id, WebhookStatus.PROCESSING)

                for attempt in range(1, settings.worker_retry_max + 1):
                    success = await self._send_webhook(webhook, attempt, db, service)

                    if success:
                        await service.update_webhook_status(webhook_id, WebhookStatus.DELIVERED)
                        logger.info(f"Webhook {webhook_id} delivered successfully")
                        return

                    if attempt < settings.worker_retry_max:
                        await asyncio.sleep(settings.worker_retry_delay)

                # Wszystkie próby nieudane
                await service.update_webhook_status(webhook_id, WebhookStatus.FAILED)
                logger.error(f"Webhook {webhook_id} failed after {settings.worker_retry_max} attempts")

    async def _send_webhook(
        self,
        webhook: Webhook,
        attempt: int,
        db,
        service: WebhookService,
    ) -> bool:
        """Wysyła pojedynczy webhook."""
        try:
            await service.add_operation(
                webhook_id=webhook.id,
                attempt=attempt,
                status=OperationStatus.IN_PROGRESS,
            )

            async with self._session.post(
                webhook.url,
                json=webhook.payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                status_code = response.status
                response_body = await response.text()

                if 200 <= status_code < 300:
                    await service.add_operation(
                        webhook_id=webhook.id,
                        attempt=attempt,
                        status=OperationStatus.SUCCESS,
                        status_code=status_code,
                        response_body=response_body[:1000],  # Ogranicz długość
                    )
                    return True
                else:
                    await service.add_operation(
                        webhook_id=webhook.id,
                        attempt=attempt,
                        status=OperationStatus.FAILED,
                        status_code=status_code,
                        response_body=response_body[:1000],
                        error_message=f"HTTP {status_code}",
                    )
                    return False

        except asyncio.TimeoutError:
            await service.add_operation(
                webhook_id=webhook.id,
                attempt=attempt,
                status=OperationStatus.FAILED,
                error_message="Request timeout",
            )
            return False

        except aiohttp.ClientError as e:
            await service.add_operation(
                webhook_id=webhook.id,
                attempt=attempt,
                status=OperationStatus.FAILED,
                error_message=f"Client error: {str(e)}",
            )
            return False

        except Exception as e:
            await service.add_operation(
                webhook_id=webhook.id,
                attempt=attempt,
                status=OperationStatus.FAILED,
                error_message=f"Unexpected error: {str(e)}",
            )
            return False


# Globalna instancja workera
worker: WebhookWorker | None = None


async def get_worker() -> WebhookWorker:
    """Zwraca instancję workera."""
    global worker
    if worker is None:
        worker = WebhookWorker()
    return worker