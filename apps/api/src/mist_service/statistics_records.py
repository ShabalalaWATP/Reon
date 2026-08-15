"""Framework-free records exchanged by statistics use cases and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from mist_service.analytics_evolution_models import OperationalFactType
from mist_service.analytics_models import ProjectionHealth
from mist_service.models import RequestStatus
from mist_service.organisation_models import OrganisationKind
from mist_service.schemas.statistics import StatisticsScope, StatisticsUnit


@dataclass(frozen=True, slots=True)
class StatisticsFact:
    """Content-minimised request measures permitted in aggregate calculations."""

    request_id: UUID
    command_unit_id: UUID | None
    ops_unit_id: UUID | None
    team_unit_id: UUID | None
    received_at: datetime
    required_by: date
    current_status: RequestStatus
    completed_at: datetime | None
    released_at: datetime | None
    clarification_count: int
    clarification_response_seconds: int
    rework_count: int
    feedback_received: bool
    feedback_rating: int | None


@dataclass(frozen=True, slots=True)
class StatisticsStageInterval:
    request_id: UUID
    status: RequestStatus
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


@dataclass(frozen=True, slots=True)
class StatisticsChild:
    id: UUID
    name: str
    kind: OrganisationKind


@dataclass(frozen=True, slots=True)
class StatisticsFreshness:
    health: ProjectionHealth
    last_projected_at: datetime | None
    source_event_count: int
    projected_request_count: int


@dataclass(frozen=True, slots=True)
class StatisticsDataset:
    scope: StatisticsScope
    selected_unit: StatisticsUnit
    breadcrumb: tuple[StatisticsUnit, ...]
    facts: tuple[StatisticsFact, ...]
    intervals: tuple[StatisticsStageInterval, ...]
    children: tuple[StatisticsChild, ...]
    freshness: StatisticsFreshness | None


@dataclass(frozen=True, slots=True)
class OperationalStatisticsFact:
    type: OperationalFactType
    occurred_at: datetime
    count_value: int
    duration_seconds: int | None
    measure_minutes: int | None


@dataclass(frozen=True, slots=True)
class StatisticsEvolutionDataset:
    current: StatisticsDataset
    previous: StatisticsDataset
    operational_facts: tuple[OperationalStatisticsFact, ...]
