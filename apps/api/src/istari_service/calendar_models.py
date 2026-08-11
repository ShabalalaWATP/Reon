"""Canonical calendar events, occurrence exceptions and capacity snapshots."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base, CreatedMixin, TimestampMixin, _enum


class CalendarCategory(StrEnum):
    AVAILABILITY = "AVAILABILITY"
    SERVICE_WORK = "SERVICE_WORK"
    LEAVE = "LEAVE"
    TRAINING = "TRAINING"
    DUTY = "DUTY"
    APPOINTMENT = "APPOINTMENT"
    OTHER = "OTHER"


class CalendarVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    AVAILABILITY_ONLY = "AVAILABILITY_ONLY"
    TEAM_DETAIL = "TEAM_DETAIL"


class RecurrenceFrequency(StrEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class CalendarEventKind(StrEnum):
    PERSONAL = "PERSONAL"
    TEAM = "TEAM"
    COMMITMENT = "COMMITMENT"


class CalendarEventStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class CommitmentStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISPUTED = "DISPUTED"


class OccurrenceExceptionKind(StrEnum):
    EDITED = "EDITED"
    CANCELLED = "CANCELLED"


class CalendarEvent(TimestampMixin, Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="calendar_event_window"),
        CheckConstraint(
            "recurrence_interval BETWEEN 1 AND 4", name="calendar_recurrence_interval"
        ),
        CheckConstraint("version > 0", name="calendar_event_version"),
        Index(
            "ix_calendar_events_subject_window",
            "subject_user_id",
            "starts_at",
            "recurrence_until",
        ),
        Index(
            "ix_calendar_events_team_window", "team_id", "starts_at", "recurrence_until"
        ),
    )

    subject_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    kind: Mapped[CalendarEventKind] = mapped_column(
        _enum(CalendarEventKind, "calendar_event_kind"), index=True
    )
    category: Mapped[CalendarCategory] = mapped_column(
        _enum(CalendarCategory, "calendar_category")
    )
    visibility: Mapped[CalendarVisibility] = mapped_column(
        _enum(CalendarVisibility, "calendar_visibility")
    )
    title: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(UTC_TS)
    ends_at: Mapped[datetime] = mapped_column(UTC_TS)
    time_zone: Mapped[str] = mapped_column(String(64))
    all_day: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    recurrence: Mapped[RecurrenceFrequency] = mapped_column(
        _enum(RecurrenceFrequency, "calendar_recurrence")
    )
    recurrence_interval: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    recurrence_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    status: Mapped[CalendarEventStatus] = mapped_column(
        _enum(CalendarEventStatus, "calendar_event_status"), index=True
    )
    commitment_status: Mapped[CommitmentStatus] = mapped_column(
        _enum(CommitmentStatus, "commitment_status")
    )
    commitment_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class CalendarOccurrenceException(TimestampMixin, Base):
    __tablename__ = "calendar_occurrence_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "occurrence_start", name="calendar_occurrence_identity"
        ),
    )

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"), index=True
    )
    occurrence_start: Mapped[datetime] = mapped_column(UTC_TS)
    kind: Mapped[OccurrenceExceptionKind] = mapped_column(
        _enum(OccurrenceExceptionKind, "calendar_exception_kind")
    )
    replacement_start: Mapped[datetime | None] = mapped_column(UTC_TS)
    replacement_end: Mapped[datetime | None] = mapped_column(UTC_TS)
    title: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    changed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class CalendarCapacityPreview(CreatedMixin, Base):
    __tablename__ = "calendar_capacity_previews"

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    time_zone: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    days: Mapped[list[dict[str, int | str]]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTC_TS)
    consumed_at: Mapped[datetime | None] = mapped_column(UTC_TS)


class CalendarCapacitySnapshot(CreatedMixin, Base):
    __tablename__ = "calendar_capacity_snapshots"

    preview_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_capacity_previews.id", ondelete="RESTRICT"), unique=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    committed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    time_zone: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    days: Mapped[list[dict[str, int | str]]] = mapped_column(JSON)
