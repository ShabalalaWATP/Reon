"""Versioned content-free analytics facts and controlled export state."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base, CreatedMixin, _enum


class OperationalFactType(StrEnum):
    NOTIFICATION_SENT = "NOTIFICATION_SENT"
    NOTIFICATION_RESPONDED = "NOTIFICATION_RESPONDED"
    DISSEMINATION_RELEASED = "DISSEMINATION_RELEASED"
    DISSEMINATION_DOWNLOADED = "DISSEMINATION_DOWNLOADED"
    DISSEMINATION_LINK_OPENED = "DISSEMINATION_LINK_OPENED"
    DISSEMINATION_REPLACED = "DISSEMINATION_REPLACED"
    DISSEMINATION_WITHDRAWN = "DISSEMINATION_WITHDRAWN"
    ITERATION_COMMITTED = "ITERATION_COMMITTED"
    ITERATION_COMPLETED = "ITERATION_COMPLETED"
    CAPACITY_AVAILABLE = "CAPACITY_AVAILABLE"
    CAPACITY_RESERVED = "CAPACITY_RESERVED"
    PLANNING_ACTIVE_WORK = "PLANNING_ACTIVE_WORK"
    PLANNING_DEMAND = "PLANNING_DEMAND"


class AnalyticsExportFormat(StrEnum):
    CSV = "CSV"
    PDF = "PDF"


class AnalyticsExportStatus(StrEnum):
    PENDING = "PENDING"
    DENIED = "DENIED"
    READY = "READY"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class AnalyticsDefinitionVersion(CreatedMixin, Base):
    __tablename__ = "analytics_definition_versions"
    __table_args__ = (
        UniqueConstraint("key", "version"),
        CheckConstraint("version > 0", name="analytics_definition_version"),
    )

    key: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(24))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )


class OperationalAnalyticsFact(CreatedMixin, Base):
    __tablename__ = "operational_analytics_facts"
    __table_args__ = (
        UniqueConstraint("source_key"),
        CheckConstraint("count_value >= 0", name="operational_fact_count"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="operational_fact_duration",
        ),
        CheckConstraint(
            "measure_minutes IS NULL OR measure_minutes >= 0",
            name="operational_fact_minutes",
        ),
        CheckConstraint("definition_version > 0", name="operational_fact_definition"),
        CheckConstraint("projection_version > 0", name="operational_fact_projection"),
        Index("ix_operational_facts_root_occurred", "root_unit_id", "occurred_at"),
        Index(
            "ix_operational_facts_command_occurred", "command_unit_id", "occurred_at"
        ),
        Index("ix_operational_facts_ops_occurred", "ops_unit_id", "occurred_at"),
        Index("ix_operational_facts_team_occurred", "team_unit_id", "occurred_at"),
        Index("ix_operational_facts_type_occurred", "type", "occurred_at"),
    )

    source_key: Mapped[str] = mapped_column(String(160))
    type: Mapped[OperationalFactType] = mapped_column(
        _enum(OperationalFactType, "operational_fact_type"), index=True
    )
    root_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT")
    )
    command_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT")
    )
    ops_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT")
    )
    team_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT")
    )
    occurred_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    count_value: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    measure_minutes: Mapped[int | None] = mapped_column(Integer)
    definition_version: Mapped[int] = mapped_column(Integer)
    projection_version: Mapped[int] = mapped_column(Integer)


class AnalyticsAggregateExport(CreatedMixin, Base):
    __tablename__ = "analytics_aggregate_exports"
    __table_args__ = (
        CheckConstraint("date_to >= date_from", name="analytics_export_window"),
        CheckConstraint("row_count >= 0", name="analytics_export_rows"),
        CheckConstraint("version > 0", name="analytics_export_version"),
        CheckConstraint(
            "status <> 'READY' OR expires_at IS NOT NULL",
            name="analytics_export_ready_expiry",
        ),
        Index("ix_analytics_exports_actor_created", "actor_user_id", "created_at"),
    )

    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    management_grant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("management_grants.id", ondelete="RESTRICT")
    )
    scope_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT")
    )
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    time_zone: Mapped[str] = mapped_column(String(64))
    format: Mapped[AnalyticsExportFormat] = mapped_column(
        _enum(AnalyticsExportFormat, "analytics_export_format")
    )
    status: Mapped[AnalyticsExportStatus] = mapped_column(
        _enum(AnalyticsExportStatus, "analytics_export_status"), index=True
    )
    query_digest: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cohort_suppressed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    reason: Mapped[str] = mapped_column(String(240))
    expires_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class AnalyticsExportAuditEvent(CreatedMixin, Base):
    __tablename__ = "analytics_export_audit_events"
    __table_args__ = (
        UniqueConstraint("export_id", "sequence"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
    )

    export_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_aggregate_exports.id", ondelete="RESTRICT"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    from_status: Mapped[AnalyticsExportStatus | None] = mapped_column(
        _enum(AnalyticsExportStatus, "analytics_export_event_from_status")
    )
    to_status: Mapped[AnalyticsExportStatus] = mapped_column(
        _enum(AnalyticsExportStatus, "analytics_export_event_to_status")
    )
    reason: Mapped[str] = mapped_column(String(240))
