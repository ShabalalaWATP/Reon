"""Narrow application ports for the advisory planning cockpit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from istari_service.board_models import TeamIteration
from istari_service.board_projection import ProjectedBoardItem
from istari_service.domain import Actor
from istari_service.management_models import ManagementAction
from istari_service.planning_analytics_models import IterationSummarySnapshot
from istari_service.planning_capacity_types import PlanningCapacityProjection
from istari_service.planning_evolution_types import (
    PackagePlanningRows,
    PlanningFreshnessState,
    ScenarioPreviewRecord,
)
from istari_service.schemas.planning import (
    CapacityBreakdown,
    CapacityConflict,
    CapacityScenarioCommand,
    CapacityScenarioSummary,
    PackageTemplateResult,
)


class PlanningAccessPolicy(Protocol):
    async def authorise_read(
        self, actor: Actor, team_id: UUID, action: ManagementAction
    ) -> None: ...

    async def authorise_preview(
        self, actor: Actor, team_id: UUID, grant_id: UUID
    ) -> None: ...


class PlanningBoardReader(Protocol):
    async def projected_items(self, team_id: UUID) -> list[ProjectedBoardItem]: ...


class PlanningQueryReader(Protocol):
    async def templates(self, team_id: UUID) -> list[PackageTemplateResult]: ...

    async def scenarios(self, team_id: UUID) -> list[CapacityScenarioSummary]: ...

    async def package_rows(self, team_id: UUID) -> PackagePlanningRows: ...

    async def request_work_count(self, team_id: UUID) -> int: ...

    async def current_iteration(
        self, team_id: UUID
    ) -> tuple[TeamIteration, IterationSummarySnapshot | None] | None: ...


class PlanningScenarioWriter(Protocol):
    async def create_scenario_preview(
        self,
        *,
        actor_id: UUID,
        team_id: UUID,
        command: CapacityScenarioCommand,
        source_version: int,
        source_digest: str,
        baseline: CapacityBreakdown,
        scenario_value: CapacityBreakdown,
        conflicts: list[CapacityConflict],
        expires_at: datetime,
    ) -> ScenarioPreviewRecord: ...


class PlanningCapacityReader(Protocol):
    async def capacity(
        self, team_id: UUID, date_from: date, date_to: date
    ) -> PlanningCapacityProjection: ...


class PlanningFreshnessReader(Protocol):
    async def freshness(self) -> PlanningFreshnessState: ...
