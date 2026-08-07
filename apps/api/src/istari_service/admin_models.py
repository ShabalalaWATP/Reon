"""Tamper-evident persistence for bounded administration events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, UUID_TYPE, Base, CreatedMixin


class AdminAuditAnchor(Base):
    __tablename__ = "admin_audit_anchors"
    __table_args__ = (
        CheckConstraint(
            "(event_count = 0 AND head_hash IS NULL AND anchor_mac IS NULL) OR "
            "(event_count > 0 AND head_hash IS NOT NULL AND anchor_mac IS NOT NULL)",
            name="admin_audit_anchor_consistency",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    head_hash: Mapped[str | None] = mapped_column(String(64))
    anchor_mac: Mapped[str | None] = mapped_column(String(64))


class AdminIdentitySequence(Base):
    __tablename__ = "admin_identity_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer)


class AdminAuditEvent(CreatedMixin, Base):
    __tablename__ = "admin_audit_events"
    __table_args__ = (UniqueConstraint("anchor_id", "sequence"),)

    anchor_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_audit_anchors.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64))
    changed_fields: Mapped[list[str]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTC_TS)


ADMIN_AUDIT_ANCHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
