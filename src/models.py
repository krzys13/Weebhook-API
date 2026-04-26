"""Modele danych dla webhooków."""
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Baza modeli SQLAlchemy."""
    pass


class WebhookStatus(str, enum.Enum):
    """Status webhooka."""
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"


class OperationStatus(str, enum.Enum):
    """Status operacji."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class Webhook(Base):
    """Model webhooka."""
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(Enum(WebhookStatus), default=WebhookStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacje
    operations: Mapped[list["Operation"]] = relationship("Operation", back_populates="webhook", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_webhook_url_status", "url", "status"),
        Index("idx_webhook_created", "created_at"),
    )


class Operation(Base):
    """Model operacji dostarczenia."""
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id: Mapped[str] = mapped_column(String(36), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[OperationStatus] = mapped_column(Enum(OperationStatus), default=OperationStatus.PENDING)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relacje
    webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="operations")

    __table_args__ = (
        Index("idx_operation_webhook", "webhook_id"),
        Index("idx_operation_status", "status"),
    )


class DeduplicationEntry(Base):
    """Model dla deduplikacji webhooków."""
    __tablename__ = "deduplication"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_dedup_url_hash", "url", "payload_hash"),
    )