"""Serwis webhooków - logika biznesowa."""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import DeduplicationEntry, Operation, OperationStatus, Webhook, WebhookStatus


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Oblicza hash payloadu dla deduplikacji."""
    payload_str = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_str.encode()).hexdigest()


class WebhookService:
    """Serwis do zarządzania webhookami."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_webhook(self, url: str, payload: dict[str, Any]) -> tuple[Webhook | None, bool]:
        """
        Tworzy nowy webhook z uwzględnieniem deduplikacji.
        Zwraca (webhook, is_duplicate).
        """
        # Sprawdź deduplikację
        is_duplicate = await self._check_duplicate(url, payload)
        if is_duplicate:
            return None, True

        # Utwórz webhook
        webhook = Webhook(url=url, payload=payload, status=WebhookStatus.PENDING)
        self.db.add(webhook)
        await self.db.flush()

        # Dodaj wpis deduplikacji
        dedup_entry = DeduplicationEntry(
            url=url,
            payload_hash=compute_payload_hash(payload),
        )
        self.db.add(dedup_entry)
        await self.db.commit()

        return webhook, False

    async def _check_duplicate(self, url: str, payload: dict[str, Any]) -> bool:
        """Sprawdza czy webhook jest duplikatem w oknie czasowym."""
        payload_hash = compute_payload_hash(payload)
        window = datetime.utcnow() - timedelta(seconds=settings.deduplication_window_seconds)
        print("CHECK DUPLICATE", url, payload_hash, window)
        stmt = select(DeduplicationEntry).where(
            DeduplicationEntry.url == url,
            DeduplicationEntry.payload_hash == payload_hash,
            DeduplicationEntry.created_at > window,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        print("EXISTING", existing)

        return existing is not None

    async def get_webhook(self, webhook_id: str) -> Webhook | None:
        """Pobiera webhook po ID."""
        stmt = select(Webhook).where(Webhook.id == webhook_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_webhooks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: WebhookStatus | None = None,
    ) -> tuple[list[Webhook], int]:
        """Lista webhooków z paginacją."""
        query = select(Webhook).order_by(Webhook.created_at.desc())

        if status:
            query = query.where(Webhook.status == status)

        # Count
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginated
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        webhooks = list(result.scalars().all())

        return webhooks, total

    async def get_webhook_detail(self, webhook_id: str) -> Webhook | None:
        """Pobiera webhook z historią operacji."""
        stmt = (
            select(Webhook)
            .where(Webhook.id == webhook_id)
            .options(selectinload(Webhook.operations))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_webhook_status(
        self,
        webhook_id: str,
        status: WebhookStatus,
    ) -> None:
        """Aktualizuje status webhooka."""
        webhook = await self.get_webhook(webhook_id)
        if webhook:
            webhook.status = status
            webhook.updated_at = datetime.utcnow()
            await self.db.commit()

    async def add_operation(
        self,
        webhook_id: str,
        attempt: int,
        status: OperationStatus,
        status_code: int | None = None,
        response_body: str | None = None,
        error_message: str | None = None,
    ) -> Operation:
        """Dodaje operację do historii."""
        operation = Operation(
            webhook_id=webhook_id,
            attempt=attempt,
            status=status,
            status_code=status_code,
            response_body=response_body,
            error_message=error_message,
            completed_at=datetime.utcnow() if status in (OperationStatus.SUCCESS, OperationStatus.FAILED) else None,
        )
        self.db.add(operation)
        await self.db.commit()
        return operation

    async def get_pending_webhooks(self, limit: int = 100) -> list[Webhook]:
        """Pobiera oczekujące webhooki do przetworzenia."""
        stmt = (
            select(Webhook)
            .where(Webhook.status == WebhookStatus.PENDING)
            .order_by(Webhook.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# Import dodatkowy
from sqlalchemy.orm import selectinload