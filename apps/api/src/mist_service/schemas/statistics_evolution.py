"""Content-free advanced statistics and controlled export contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from mist_service.analytics_evolution_models import AnalyticsExportFormat
from mist_service.schemas.common import ApiModel, StrictApiModel
from mist_service.schemas.statistics import (
    ProjectionFreshness,
    StatisticsRange,
    StatisticsScope,
    StatisticsUnit,
)


class PeriodComparison(ApiModel):
    key: str
    label: str
    current: int | float | None
    previous: int | float | None
    change: int | float | None
    unit: Literal["count", "percentage", "hours"]
    suppressed: bool = False


class BottleneckMeasure(ApiModel):
    key: str
    label: str
    active_count: int | None = Field(default=None, ge=0)
    median_age_hours: float | None = Field(default=None, ge=0)
    p90_age_hours: float | None = Field(default=None, ge=0)
    overdue_count: int | None = Field(default=None, ge=0)
    suppressed: bool


class CapacityMeasure(ApiModel):
    date: date
    available_minutes: int = Field(ge=0)
    reserved_minutes: int = Field(ge=0)
    active_work_minutes: int = Field(ge=0)
    projected_demand_minutes: int = Field(ge=0)
    estimate: bool


class ReleaseMeasure(ApiModel):
    key: str
    label: str
    count: int | None = Field(default=None, ge=0)
    median_hours: float | None = Field(default=None, ge=0)
    suppressed: bool


class NotificationMeasure(ApiModel):
    key: str
    label: str
    count: int | None = Field(default=None, ge=0)
    median_response_hours: float | None = Field(default=None, ge=0)
    unresolved_count: int | None = Field(default=None, ge=0)
    suppressed: bool


class IterationMeasure(ApiModel):
    key: str
    label: str
    committed_count: int | None = Field(default=None, ge=0)
    completed_count: int | None = Field(default=None, ge=0)
    completion_percentage: float | None = Field(default=None, ge=0, le=100)
    suppressed: bool


class ProjectionPeriod(ApiModel):
    date: date
    demand_count: int = Field(ge=0)
    capacity_count: int = Field(ge=0)


class DemandCapacityProjection(ApiModel):
    label: str
    estimate: Literal[True] = True
    periods: list[ProjectionPeriod]


class ExportPolicy(ApiModel):
    state: Literal["AVAILABLE", "DENIED", "SUPPRESSED", "PENDING"]
    reason: str


class ExportPolicies(ApiModel):
    csv: ExportPolicy
    pdf: ExportPolicy


class StatisticsEvolution(ApiModel):
    scope: StatisticsScope
    selected_unit: StatisticsUnit
    breadcrumb: list[StatisticsUnit]
    range: StatisticsRange
    freshness: ProjectionFreshness
    comparison: list[PeriodComparison]
    bottlenecks: list[BottleneckMeasure]
    capacity: list[CapacityMeasure]
    releases: list[ReleaseMeasure]
    notifications: list[NotificationMeasure]
    iterations: list[IterationMeasure]
    projection: DemandCapacityProjection
    exports: ExportPolicies


class StatisticsExportCommand(StrictApiModel):
    scope_id: str = Field(min_length=1, max_length=80)
    unit_id: UUID | None = None
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    time_zone: str = Field(min_length=1, max_length=64)
    format: AnalyticsExportFormat

    @model_validator(mode="after")
    def valid_window(self) -> StatisticsExportCommand:
        if self.to_date < self.from_date:
            raise ValueError("The end date must be on or after the start date.")
        if (self.to_date - self.from_date).days > 365:
            raise ValueError("Statistics are limited to 366 days.")
        return self


class StatisticsExportResult(ApiModel):
    state: Literal["READY", "PENDING"]
    download_url: str | None
    expires_at: datetime | None
    message: str
