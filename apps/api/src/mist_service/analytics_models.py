"""Content-minimised operational analytics projections."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.models import (
    UTC_TS,
    UUID_TYPE,
    Base,
    CreatedMixin,
    RequestStatus,
    _enum,
)


class ProjectionHealth(StrEnum):
    READY = "READY"
    REBUILDING = "REBUILDING"
    DEGRADED = "DEGRADED"


class RequestAnalyticsFact(Base):
    __tablename__ = "request_analytics_facts"
    __table_args__ = (
        CheckConstraint("clarification_count >= 0", name="fact_clarifications"),
        CheckConstraint(
            "clarification_response_seconds >= 0",
            name="fact_clarification_response_seconds",
        ),
        CheckConstraint("rework_count >= 0", name="fact_rework"),
        CheckConstraint(
            "feedback_rating IS NULL OR feedback_rating BETWEEN 1 AND 5",
            name="fact_feedback_rating",
        ),
        CheckConstraint("projection_version > 0", name="fact_projection_version"),
        CheckConstraint("source_event_count >= 0", name="fact_source_event_count"),
        Index("ix_request_facts_received_status", "received_at", "current_status"),
        Index("ix_request_facts_command_received", "command_unit_id", "received_at"),
        Index("ix_request_facts_ops_received", "ops_unit_id", "received_at"),
        Index("ix_request_facts_team_received", "team_unit_id", "received_at"),
        Index("ix_analytics_team_request", "team_unit_id", "request_id"),
    )

    request_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        primary_key=True,
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
    received_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    required_by: Mapped[date] = mapped_column(index=True)
    current_status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "analytics_request_status"), index=True
    )
    last_transition_at: Mapped[datetime] = mapped_column(UTC_TS)
    completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    closed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    released_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    clarification_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    clarification_response_seconds: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    rework_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    feedback_received: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    feedback_rating: Mapped[int | None] = mapped_column(Integer)
    projection_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    source_event_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    projected_at: Mapped[datetime] = mapped_column(UTC_TS)


class RequestStageInterval(CreatedMixin, Base):
    __tablename__ = "request_stage_intervals"
    __table_args__ = (
        UniqueConstraint("request_id", "sequence"),
        CheckConstraint("sequence > 0", name="stage_interval_sequence"),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="stage_interval_window",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="stage_interval_duration",
        ),
        Index("ix_stage_intervals_status_started", "status", "started_at"),
        Index("ix_stage_intervals_unit_started", "unit_id", "started_at"),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "analytics_stage_status")
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(UTC_TS)
    ended_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    source_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("request_events.id", ondelete="SET NULL")
    )


class AnalyticsProjectionState(Base):
    __tablename__ = "analytics_projection_state"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    projection_version: Mapped[int] = mapped_column(Integer)
    health: Mapped[ProjectionHealth] = mapped_column(
        _enum(ProjectionHealth, "analytics_projection_health")
    )
    source_event_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    projected_request_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    last_projected_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    updated_at: Mapped[datetime] = mapped_column(
        UTC_TS, server_default=func.now(), onupdate=func.now()
    )
