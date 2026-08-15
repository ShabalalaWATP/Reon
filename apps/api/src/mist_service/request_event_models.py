"""Append-only request event persistence model."""

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as rel

from mist_service.models import Base, CreatedMixin, RequestStatus, User, _enum
from mist_service.request_event_audience import RequestEventAudience


class RequestEvent(CreatedMixin, Base):
    __tablename__ = "request_events"
    __table_args__ = (
        UniqueConstraint("event_hash", name="uq_request_events_event_hash"),
        CheckConstraint("hash_version IN (1, 2)", name="request_event_hash_version"),
        Index("ix_request_events_request_created", "request_id", "created_at"),
        Index(
            "ix_request_events_request_created_id",
            "request_id",
            "created_at",
            "id",
        ),
    )

    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    audience: Mapped[RequestEventAudience] = mapped_column(
        _enum(RequestEventAudience, "request_event_audience"),
        default=RequestEventAudience.STAFF_ONLY,
        server_default=RequestEventAudience.STAFF_ONLY.value,
        index=True,
    )
    prior_status: Mapped[RequestStatus | None] = mapped_column(
        _enum(RequestStatus, "event_prior_status")
    )
    next_status: Mapped[RequestStatus | None] = mapped_column(
        _enum(RequestStatus, "event_next_status")
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    audit_key_id: Mapped[str] = mapped_column(
        String(64), default="legacy", server_default="legacy"
    )
    hash_version: Mapped[int] = mapped_column(Integer, default=2, server_default="1")
    actor: Mapped[User | None] = rel(foreign_keys=[actor_user_id])
