"""Content-free, table-first operational statistics contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from mist_service.analytics_models import ProjectionHealth
from mist_service.organisation_models import OrganisationKind
from mist_service.schemas.common import ApiModel


class StatisticsUnit(ApiModel):
    id: UUID
    parent_id: UUID | None
    name: str
    kind: OrganisationKind
    depth: int = Field(ge=0)


class StatisticsScope(ApiModel):
    id: str
    unit_id: UUID | None
    name: str
    kind: OrganisationKind | Literal["PLATFORM"]
    include_descendants: bool
    units: list[StatisticsUnit] = Field(default_factory=list)


class StatisticsScopeList(ApiModel):
    items: list[StatisticsScope]


class StatisticsRange(ApiModel):
    from_date: date
    to_date: date
    time_zone: str
    as_of_date: date


class ProjectionFreshness(ApiModel):
    health: ProjectionHealth
    last_projected_at: datetime | None
    source_event_count: int = Field(ge=0)
    projected_request_count: int = Field(ge=0)


class MetricDefinition(ApiModel):
    key: str
    label: str
    description: str


class SummaryMetric(ApiModel):
    key: str
    label: str
    value: int | float | None
    unit: Literal["count", "percentage", "rating", "hours"]
    suppressed: bool = False


class CategoryCount(ApiModel):
    key: str
    label: str
    count: int = Field(ge=0)


class DailyThroughput(ApiModel):
    date: date
    received: int = Field(ge=0)
    completed: int = Field(ge=0)


class StageDuration(ApiModel):
    key: str
    label: str
    completed_intervals: int = Field(ge=0)
    median_hours: float
    p90_hours: float


class ChildUnitComparison(ApiModel):
    unit_id: UUID
    name: str
    kind: OrganisationKind
    received: int = Field(ge=0)
    active: int = Field(ge=0)
    completed: int = Field(ge=0)
    overdue: int = Field(ge=0)
    feedback_count: int = Field(ge=0)
    average_rating: float | None
    rating_suppressed: bool


class StatisticsDashboard(ApiModel):
    scope: StatisticsScope
    selected_unit: StatisticsUnit
    breadcrumb: list[StatisticsUnit]
    range: StatisticsRange
    freshness: ProjectionFreshness
    definitions: list[MetricDefinition]
    summary: list[SummaryMetric]
    status: list[CategoryCount]
    age: list[CategoryCount]
    due_risk: list[CategoryCount]
    throughput_resolution: Literal["DAILY", "WEEKLY", "MONTHLY"]
    throughput: list[DailyThroughput]
    stage_durations: list[StageDuration]
    children: list[ChildUnitComparison]
