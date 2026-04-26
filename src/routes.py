"""REST API dla webhook delivery system."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import (
    HealthResponse,
    OperationResponse,
    WebhookCreate,
    WebhookDetailResponse,
    WebhookListResponse,
    WebhookResponse,
)
from .service import WebhookService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", database="ok")


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Tworzy nowy webhook.
    Endpoint przyjmuje URL i payload, zapisuje zlecenie i zwraca potwierdzenie.
    """
    service = WebhookService(db)
    webhook, is_duplicate = await service.create_webhook(
        url=str(webhook_data.url),
        payload=webhook_data.payload,
    )

    if is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate webhook request within deduplication window",
        )

    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        payload=webhook.payload,
        status=webhook.status.value,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@router.get("/webhooks", response_model=WebhookListResponse)
async def list_webhooks(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """
    Pobiera listę webhooków z paginacją.
    """
    service = WebhookService(db)
    webhooks, total = await service.list_webhooks(page=page, page_size=page_size)

    items = [
        WebhookResponse(
            id=w.id,
            url=w.url,
            payload=w.payload,
            status=w.status.value,
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w in webhooks
    ]

    return WebhookListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/webhooks/{webhook_id}", response_model=WebhookDetailResponse)
async def get_webhook(
    webhook_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Pobiera szczegóły webhooka wraz z historią operacji.
    """
    service = WebhookService(db)
    webhook = await service.get_webhook_detail(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    operations = [
        OperationResponse(
            id=op.id,
            webhook_id=op.webhook_id,
            attempt=op.attempt,
            status=op.status.value,
            status_code=op.status_code,
            response_body=op.response_body,
            error_message=op.error_message,
            created_at=op.created_at,
            completed_at=op.completed_at,
        )
        for op in webhook.operations
    ]

    return WebhookDetailResponse(
        id=webhook.id,
        url=webhook.url,
        payload=webhook.payload,
        status=webhook.status.value,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
        operations=operations,
    )


@router.get("/webhooks/{webhook_id}/history", response_model=list[OperationResponse])
async def get_webhook_history(
    webhook_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Pobiera historię operacji dla webhooka.
    """
    service = WebhookService(db)
    webhook = await service.get_webhook_detail(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    return [
        OperationResponse(
            id=op.id,
            webhook_id=op.webhook_id,
            attempt=op.attempt,
            status=op.status.value,
            status_code=op.status_code,
            response_body=op.response_body,
            error_message=op.error_message,
            created_at=op.created_at,
            completed_at=op.completed_at,
        )
        for op in webhook.operations
    ]