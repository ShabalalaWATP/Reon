"""Effective request leadership and contributor assignments."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base, TimestampMixin, _enum


class RequestParticipantRole(StrEnum):
    LEAD = "LEAD"
    CONTRIBUTOR = "CONTRIBUTOR"


class RequestParticipant(TimestampMixin, Base):
    __tablename__ = "request_participants"
    __table_args__ = (
        CheckConstraint("version > 0", name="request_participant_version"),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= effective_from",
            name="request_participant_window",
        ),
        Index(
            "uq_request_participants_active_user",
            "request_id",
            "user_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "uq_request_participants_active_lead",
            "request_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL AND role = 'LEAD'"),
            postgresql_where=text("ended_at IS NULL AND role = 'LEAD'"),
        ),
        Index("ix_request_participants_user_active", "user_id", "ended_at"),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[RequestParticipantRole] = mapped_column(
        _enum(RequestParticipantRole, "request_participant_role"), index=True
    )
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[datetime] = mapped_column(UTC_TS)
    ended_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    ended_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    end_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
