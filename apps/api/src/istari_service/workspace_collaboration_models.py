"""Bounded collaboration records attached to organisation workspaces."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import Base, CreatedMixin, TimestampMixin, _enum


class WorkspaceRecordKind(StrEnum):
    DESCRIPTION = "DESCRIPTION"
    HANDOVER = "HANDOVER"
    RISK = "RISK"
    BLOCKER = "BLOCKER"
    DECISION = "DECISION"
    LINK = "LINK"


class WorkspaceRecordStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class WorkspaceRecordEventType(StrEnum):
    CREATED = "CREATED"
    RESOLVED = "RESOLVED"


class WorkspaceRecord(TimestampMixin, Base):
    __tablename__ = "workspace_records"
    __table_args__ = (
        CheckConstraint("version > 0", name="workspace_record_version"),
        Index("ix_workspace_records_unit_status", "unit_id", "status", "updated_at"),
    )

    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[WorkspaceRecordKind] = mapped_column(
        _enum(WorkspaceRecordKind, "workspace_record_kind"), index=True
    )
    status: Mapped[WorkspaceRecordStatus] = mapped_column(
        _enum(WorkspaceRecordStatus, "workspace_record_status"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class WorkspaceRecordEvent(CreatedMixin, Base):
    """Immutable audit fact for each collaboration-record transition."""

    __tablename__ = "workspace_record_events"
    __table_args__ = (
        Index("ix_workspace_record_events_record_created", "record_id", "created_at"),
    )

    record_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspace_records.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    type: Mapped[WorkspaceRecordEventType] = mapped_column(
        _enum(WorkspaceRecordEventType, "workspace_record_event_type"), index=True
    )
    record_version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(240))
