"""Advisory team-planning cockpit and capacity scenario contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from mist_service.planning_analytics_models import PlanningScenarioStatus
from mist_service.schemas.common import ApiModel, StrictApiModel


class PlanningFreshness(ApiModel):
    health: Literal["READY", "STALE", "REBUILDING"]
    label: str
    source_version: int = Field(ge=1)


class PlanningSummary(ApiModel):
    backlog_count: int = Field(ge=0)
    active_iteration_count: int = Field(ge=0)
    due_risk_count: int = Field(ge=0)
    wip_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    available_minutes: int = Field(ge=0)
    reserved_minutes: int = Field(ge=0)


class PlanningLaneItem(ApiModel):
    id: UUID
    kind: Literal["REQUEST", "PACKAGE"]
    reference: str
    title: str
    owner_display_name: str | None
    priority: str
    due_on: date
    status: str
    iteration_name: str | None
    blocker_age_days: int | None = Field(default=None, ge=0)
    dependency_warning_count: int = Field(ge=0)


class PlanningLane(ApiModel):
    key: str
    label: str
    items: list[PlanningLaneItem]


class BlockerWarning(ApiModel):
    package_id: UUID
    reference: str
    title: str
    age_days: int = Field(ge=0)
    reason: str


class DependencyWarning(ApiModel):
    package_id: UUID
    reference: str
    title: str
    dependency_reference: str
    status: Literal["CLEAR", "AT_RISK", "BLOCKED", "MISSING"]
    warning: str


class IterationProjection(ApiModel):
    id: UUID
    name: str
    goal: str
    starts_on: date
    ends_on: date
    status: str
    committed_points: int = Field(ge=0)
    completed_points: int = Field(ge=0)
    committed_packages: int = Field(ge=0)
    completed_packages: int = Field(ge=0)
    factual_summary: str | None


class ChecklistItem(ApiModel):
    id: UUID
    label: str
    required: bool
    completed: bool


class PackageChecklistResult(ApiModel):
    package_id: UUID
    package_title: str
    template_name: str
    completed_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    items: list[ChecklistItem]


class PlanningCockpit(ApiModel):
    team_id: UUID
    generated_at: datetime
    advisory_only: Literal[True] = True
    freshness: PlanningFreshness
    summary: PlanningSummary
    lanes: list[PlanningLane]
    blockers: list[BlockerWarning]
    dependencies: list[DependencyWarning]
    iteration: IterationProjection | None
    checklists: list[PackageChecklistResult]


class TemplateChecklistItem(ApiModel):
    id: UUID
    label: str
    required: bool


class PackageTemplateResult(ApiModel):
    id: UUID
    name: str
    description: str
    version: int = Field(ge=1)
    checklist: list[TemplateChecklistItem]


class PackageTemplateList(ApiModel):
    items: list[PackageTemplateResult]


class CapacityScenarioSummary(ApiModel):
    id: UUID
    name: str
    version: int = Field(ge=1)
    starts_on: date
    ends_on: date
    status: PlanningScenarioStatus
    updated_at: datetime


class CapacityScenarioList(ApiModel):
    items: list[CapacityScenarioSummary]


class CapacityBreakdown(ApiModel):
    available_minutes: int = Field(ge=0)
    reserved_minutes: int = Field(ge=0)
    request_work_minutes: int = Field(ge=0)
    package_minutes: int = Field(ge=0)
    net_minutes: int


class CapacityConflict(ApiModel):
    date: date
    kind: Literal["CAPACITY", "CALENDAR", "RESERVATION", "DEPENDENCY"]
    summary: str


class CapacityScenarioPreview(ApiModel):
    token: str
    expires_at: datetime
    source_version: int = Field(ge=1)
    baseline: CapacityBreakdown
    scenario: CapacityBreakdown
    conflicts: list[CapacityConflict]
    estimate_label: str


class CapacityScenarioCommand(StrictApiModel):
    grant_id: UUID
    name: str = Field(min_length=3, max_length=100)
    starts_on: date
    ends_on: date
    planned_minutes: int = Field(ge=30, le=1_000_000)
    expected_source_version: int = Field(ge=1)

    @model_validator(mode="after")
    def valid_window(self) -> CapacityScenarioCommand:
        if self.ends_on < self.starts_on:
            raise ValueError("The scenario end cannot precede its start.")
        if (self.ends_on - self.starts_on).days > 90:
            raise ValueError("Scenarios are limited to 91 days.")
        return self
