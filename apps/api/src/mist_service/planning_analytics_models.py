"""Versioned team-planning records and content-free operational facts."""

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

from mist_service.models import UTC_TS, Base, CreatedMixin, TimestampMixin, _enum


class PlanningScenarioStatus(StrEnum):
    DRAFT = "DRAFT"
    PREVIEWED = "PREVIEWED"
    COMMITTED = "COMMITTED"


class PackageTemplate(TimestampMixin, Base):
    __tablename__ = "package_templates"
    __table_args__ = (
        UniqueConstraint("team_id", "name", "version"),
        CheckConstraint("version > 0", name="package_template_version"),
        Index("ix_package_templates_team_active", "team_id", "is_active"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class PackageTemplateChecklistItem(CreatedMixin, Base):
    __tablename__ = "package_template_checklist_items"
    __table_args__ = (
        UniqueConstraint("template_id", "position"),
        CheckConstraint("position >= 0", name="template_checklist_position"),
    )

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("package_templates.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(240))
    required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )


class PackageChecklist(TimestampMixin, Base):
    __tablename__ = "package_checklists"
    __table_args__ = (
        UniqueConstraint("package_id"),
        CheckConstraint("template_version > 0", name="checklist_template_version"),
        CheckConstraint("version > 0", name="package_checklist_version"),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("package_templates.id", ondelete="RESTRICT")
    )
    template_name: Mapped[str] = mapped_column(String(100))
    template_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PackageChecklistItem(TimestampMixin, Base):
    __tablename__ = "package_checklist_items"
    __table_args__ = (
        UniqueConstraint("checklist_id", "position"),
        CheckConstraint("position >= 0", name="package_checklist_item_position"),
        CheckConstraint("version > 0", name="package_checklist_item_version"),
    )

    checklist_id: Mapped[UUID] = mapped_column(
        ForeignKey("package_checklists.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(240))
    required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PackageBlocker(TimestampMixin, Base):
    __tablename__ = "package_blockers"
    __table_args__ = (
        CheckConstraint("version > 0", name="package_blocker_version"),
        CheckConstraint(
            "(resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="package_blocker_resolution_shape",
        ),
        Index("ix_package_blockers_team_opened", "team_id", "resolved_at"),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(UTC_TS)
    opened_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PlanningScenario(TimestampMixin, Base):
    __tablename__ = "planning_scenarios"
    __table_args__ = (
        UniqueConstraint("team_id", "name", "version"),
        CheckConstraint("ends_on >= starts_on", name="planning_scenario_window"),
        CheckConstraint("planned_minutes > 0", name="planning_scenario_minutes"),
        CheckConstraint("source_version > 0", name="planning_scenario_source"),
        CheckConstraint("version > 0", name="planning_scenario_version"),
        Index("ix_planning_scenarios_team_updated", "team_id", "updated_at"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    planned_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[PlanningScenarioStatus] = mapped_column(
        _enum(PlanningScenarioStatus, "planning_scenario_status"), index=True
    )
    source_version: Mapped[int] = mapped_column(Integer)
    source_digest: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PlanningCapacityPreview(CreatedMixin, Base):
    __tablename__ = "planning_capacity_previews"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="planning_preview_expiry"),
        CheckConstraint("source_version > 0", name="planning_preview_source"),
    )

    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_scenarios.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    source_digest: Mapped[str] = mapped_column(String(64))
    baseline: Mapped[dict[str, int]] = mapped_column(JSON)
    scenario: Mapped[dict[str, int]] = mapped_column(JSON)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTC_TS)
    consumed_at: Mapped[datetime | None] = mapped_column(UTC_TS)


class IterationSummarySnapshot(CreatedMixin, Base):
    __tablename__ = "iteration_summary_snapshots"
    __table_args__ = (
        UniqueConstraint("iteration_id", "source_version"),
        CheckConstraint("source_version > 0", name="iteration_summary_version"),
        CheckConstraint(
            "committed_packages >= completed_packages",
            name="iteration_summary_package_counts",
        ),
        CheckConstraint(
            "committed_points >= completed_points",
            name="iteration_summary_point_counts",
        ),
    )

    iteration_id: Mapped[UUID] = mapped_column(
        ForeignKey("team_iterations.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    source_version: Mapped[int] = mapped_column(Integer)
    committed_packages: Mapped[int] = mapped_column(Integer)
    completed_packages: Mapped[int] = mapped_column(Integer)
    committed_points: Mapped[int] = mapped_column(Integer)
    completed_points: Mapped[int] = mapped_column(Integer)
    factual_summary: Mapped[str] = mapped_column(String(240))
