"""Workflow-derived board settings and independent team planning aggregates."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
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

from istari_service.models import (
    UTC_TS,
    UUID_TYPE,
    Base,
    CreatedMixin,
    TimestampMixin,
    _enum,
)


class BoardColumn(StrEnum):
    AWAITING_ASSIGNMENT = "AWAITING_ASSIGNMENT"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    MANAGER_REVIEW = "MANAGER_REVIEW"
    QUALITY_REVIEW = "QUALITY_REVIEW"
    REWORK = "REWORK"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    BACKLOG = "BACKLOG"
    CANCELLED = "CANCELLED"


class WorkPackageStatus(StrEnum):
    BACKLOG = "BACKLOG"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class WorkPackagePriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class WorkPackageActivityType(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    MOVED = "MOVED"
    RESERVATION_CREATED = "RESERVATION_CREATED"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    ITERATION_CHANGED = "ITERATION_CHANGED"


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class IterationStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TeamIteration(TimestampMixin, Base):
    __tablename__ = "team_iterations"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="iteration_window"),
        CheckConstraint("version > 0", name="iteration_version"),
        UniqueConstraint("team_id", "name"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    goal: Mapped[str] = mapped_column(Text)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[IterationStatus] = mapped_column(
        _enum(IterationStatus, "iteration_status"), index=True
    )
    completion_summary: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class WorkPackage(TimestampMixin, Base):
    __tablename__ = "work_packages"
    __table_args__ = (
        CheckConstraint("estimate_points BETWEEN 1 AND 100", name="package_estimate"),
        CheckConstraint(
            "remaining_effort_minutes >= 0", name="package_remaining_effort"
        ),
        CheckConstraint("version > 0", name="package_version"),
        Index("ix_work_packages_team_status_due", "team_id", "status", "due_on"),
        Index("ix_work_packages_team_updated_id", "team_id", "updated_at", "id"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    linked_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), index=True
    )
    iteration_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("team_iterations.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    estimate_points: Mapped[int] = mapped_column(Integer)
    remaining_effort_minutes: Mapped[int] = mapped_column(Integer)
    due_on: Mapped[date] = mapped_column(Date, index=True)
    priority: Mapped[WorkPackagePriority] = mapped_column(
        _enum(WorkPackagePriority, "work_package_priority"), index=True
    )
    status: Mapped[WorkPackageStatus] = mapped_column(
        _enum(WorkPackageStatus, "work_package_status"), index=True
    )
    blockers: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class WorkPackageContributor(Base):
    __tablename__ = "work_package_contributors"

    package_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("work_packages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )


class WorkPackageDependency(Base):
    __tablename__ = "work_package_dependencies"
    __table_args__ = (
        CheckConstraint(
            "package_id <> depends_on_id", name="package_not_self_dependency"
        ),
    )

    package_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("work_packages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("work_packages.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class WorkPackageActivity(CreatedMixin, Base):
    __tablename__ = "work_package_activity"
    __table_args__ = (
        Index("ix_package_activity_package_created", "package_id", "created_at"),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    type: Mapped[WorkPackageActivityType] = mapped_column(
        _enum(WorkPackageActivityType, "work_package_activity_type")
    )
    summary: Mapped[str] = mapped_column(String(240))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CapacityReservation(TimestampMixin, Base):
    __tablename__ = "capacity_reservations"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="reservation_window"),
        CheckConstraint("minutes > 0", name="reservation_minutes"),
        CheckConstraint("version > 0", name="reservation_version"),
        Index(
            "ix_capacity_reservations_user_window", "user_id", "starts_at", "ends_at"
        ),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(UTC_TS)
    ends_at: Mapped[datetime] = mapped_column(UTC_TS)
    minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReservationStatus] = mapped_column(
        _enum(ReservationStatus, "reservation_status"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class TeamBoardConfiguration(Base):
    __tablename__ = "team_board_configurations"

    team_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("organisation_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    wip_limits: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class SavedBoardView(TimestampMixin, Base):
    __tablename__ = "saved_board_views"
    __table_args__ = (UniqueConstraint("team_id", "owner_user_id", "name"),)

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
