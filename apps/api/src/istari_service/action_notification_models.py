"""Durable action projections and content-minimised in-application notifications."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import (
    UTC_TS,
    Base,
    CreatedMixin,
    TimestampMixin,
    UserRole,
    _enum,
)


class ActionSection(StrEnum):
    NEEDS_MY_ACTION = "NEEDS_MY_ACTION"
    WAITING = "WAITING"
    DUE_SOON = "DUE_SOON"
    RECENTLY_COMPLETED = "RECENTLY_COMPLETED"


class ActionSourceType(StrEnum):
    WORKFLOW_TASK = "WORKFLOW_TASK"
    CLARIFICATION = "CLARIFICATION"
    PRODUCT = "PRODUCT"
    FEEDBACK = "FEEDBACK"
    CONFIGURATION = "CONFIGURATION"
    OPERATIONAL_EXCEPTION = "OPERATIONAL_EXCEPTION"


class NotificationEventGroup(StrEnum):
    REQUEST_LIFECYCLE = "REQUEST_LIFECYCLE"
    ASSIGNMENT = "ASSIGNMENT"
    CLARIFICATION = "CLARIFICATION"
    DUE_DATE = "DUE_DATE"
    REVIEW = "REVIEW"
    RELEASE = "RELEASE"
    FEEDBACK = "FEEDBACK"
    TEAM_PLANNING = "TEAM_PLANNING"
    CONFIGURATION = "CONFIGURATION"
    ACCOUNT_SECURITY = "ACCOUNT_SECURITY"


class NotificationProjectionStatus(StrEnum):
    PENDING = "PENDING"
    PROJECTED = "PROJECTED"
    FAILED = "FAILED"


class NotificationAccessKind(StrEnum):
    ACCOUNT = "ACCOUNT"
    REQUESTER = "REQUESTER"
    ASSIGNEE = "ASSIGNEE"
    ROUTE_MEMBER = "ROUTE_MEMBER"
    ROLE_SCOPE = "ROLE_SCOPE"


class ProjectionHealth(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    DEGRADED = "DEGRADED"


class ActionProjection(TimestampMixin, Base):
    __tablename__ = "action_projections"
    __table_args__ = (
        CheckConstraint(
            "recipient_user_id IS NOT NULL OR candidate_role IS NOT NULL",
            name="action_audience",
        ),
        CheckConstraint("source_version > 0", name="action_source_version"),
        CheckConstraint("version > 0", name="action_version"),
        Index(
            "ix_action_projections_recipient_section_changed",
            "recipient_user_id",
            "section",
            "last_changed_at",
        ),
        Index(
            "ix_action_projections_role_unit_section",
            "candidate_role",
            "organisation_unit_id",
            "section",
        ),
    )

    stable_key: Mapped[str] = mapped_column(String(160), unique=True)
    source_type: Mapped[ActionSourceType] = mapped_column(
        _enum(ActionSourceType, "action_source_type")
    )
    source_id: Mapped[str] = mapped_column(String(160))
    source_version: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    recipient_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    candidate_role: Mapped[UserRole | None] = mapped_column(
        _enum(UserRole, "action_candidate_role"), index=True
    )
    required_scope: Mapped[str | None] = mapped_column(String(120))
    organisation_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), index=True
    )
    section: Mapped[ActionSection] = mapped_column(
        _enum(ActionSection, "action_section"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(80), index=True)
    reference: Mapped[str] = mapped_column(String(64))
    safe_title: Mapped[str | None] = mapped_column(String(160))
    current_owner: Mapped[str] = mapped_column(String(120))
    required_by: Mapped[date | None] = mapped_column(Date, index=True)
    last_changed_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    deep_link: Mapped[str] = mapped_column(String(240))
    projected_at: Mapped[datetime] = mapped_column(UTC_TS)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class SavedActionView(TimestampMixin, Base):
    __tablename__ = "saved_action_views"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name"),
        CheckConstraint("version > 0", name="saved_action_view_version"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    visible_columns: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class NotificationEvent(CreatedMixin, Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        CheckConstraint("source_version > 0", name="notification_source_version"),
        CheckConstraint("attempts >= 0", name="notification_attempts"),
        Index(
            "ix_notification_events_status_available",
            "status",
            "available_at",
        ),
    )

    stable_key: Mapped[str] = mapped_column(String(160), unique=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    event_group: Mapped[NotificationEventGroup] = mapped_column(
        _enum(NotificationEventGroup, "notification_event_group"), index=True
    )
    source_version: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    safe_subject: Mapped[str] = mapped_column(String(180))
    deep_link: Mapped[str | None] = mapped_column(String(240))
    audience: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, default=list)
    occurred_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    status: Mapped[NotificationProjectionStatus] = mapped_column(
        _enum(NotificationProjectionStatus, "notification_projection_status"),
        default=NotificationProjectionStatus.PENDING,
        server_default=NotificationProjectionStatus.PENDING.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    projected_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    last_error: Mapped[str | None] = mapped_column(Text)


class NotificationRecipient(TimestampMixin, Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint("notification_event_id", "recipient_user_id"),
        CheckConstraint("version > 0", name="notification_recipient_version"),
        Index(
            "ix_notification_recipients_user_state",
            "recipient_user_id",
            "archived_at",
            "read_at",
        ),
    )

    notification_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_events.id", ondelete="CASCADE"), index=True
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    access_kind: Mapped[NotificationAccessKind] = mapped_column(
        _enum(NotificationAccessKind, "notification_access_kind")
    )
    required_role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "notification_required_role")
    )
    required_scope: Mapped[str | None] = mapped_column(String(120))
    organisation_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    archived_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    action_completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "event_group"),
        CheckConstraint("version > 0", name="notification_preference_version"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_group: Mapped[NotificationEventGroup] = mapped_column(
        _enum(NotificationEventGroup, "notification_preference_group")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    reminder_days: Mapped[list[int]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ProjectionCheckpoint(Base):
    __tablename__ = "projection_checkpoints"
    __table_args__ = (
        CheckConstraint("pending_count >= 0", name="projection_pending_count"),
        CheckConstraint("failed_count >= 0", name="projection_failed_count"),
    )

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_event_key: Mapped[str | None] = mapped_column(String(160))
    source_changed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    projected_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    pending_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    health: Mapped[ProjectionHealth] = mapped_column(
        _enum(ProjectionHealth, "projection_health"),
        default=ProjectionHealth.DEGRADED,
        server_default=ProjectionHealth.DEGRADED.value,
    )
