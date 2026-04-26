"""Schematy Pydantic dla webhooków."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreate(BaseModel):
    """Schemat tworzenia webhooka."""
    url: HttpUrl = Field(..., description="URL docelowy dla webhooka")
    payload: dict[str, Any] = Field(..., description="Dane do wysłania")


class WebhookResponse(BaseModel):
    """Schemat odpowiedzi webhooka."""
    id: str
    url: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OperationResponse(BaseModel):
    """Schemat operacji."""
    id: str
    webhook_id: str
    attempt: int
    status: str
    status_code: int | None
    response_body: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class WebhookDetailResponse(WebhookResponse):
    """Szczegółowa odpowiedź webhooka z historią operacji."""
    operations: list[OperationResponse] = []


class WebhookListResponse(BaseModel):
    """Lista webhooków z paginacją."""
    items: list[WebhookResponse]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    """Odpowiedź health check."""
    status: str
    database: str