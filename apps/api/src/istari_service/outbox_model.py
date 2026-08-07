"""Transactional outbox persistence kept separate from core domain rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import Base, OutboxStatus, TimestampMixin, _enum

OUTBOX_UTC_TS = DateTime(timezone=True)


class WorkflowOutbox(TimestampMixin, Base):
    __tablename__ = "workflow_outbox"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    status: Mapped[OutboxStatus] = mapped_column(
        _enum(OutboxStatus, "outbox_status"), default=OutboxStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(64))
    lease_generation: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    available_at: Mapped[datetime] = mapped_column(
        OUTBOX_UTC_TS, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(OUTBOX_UTC_TS)
    last_error: Mapped[str | None] = mapped_column(Text)
