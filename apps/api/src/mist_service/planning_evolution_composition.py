"""Transaction-scoped composition for the advisory planning cockpit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.analytics_models import AnalyticsProjectionState, ProjectionHealth
from mist_service.analytics_projection import PROJECTION_NAME
from mist_service.domain import Actor
from mist_service.management_models import ManagementAction
from mist_service.planning_capacity import calculate_planning_capacity
from mist_service.planning_capacity_types import PlanningCapacityProjection
from mist_service.planning_evolution_types import PlanningFreshnessState
from mist_service.planning_policy import (
    authorise_planning_preview,
    authorise_planning_read,
)
from mist_service.repositories.board import SqlAlchemyBoardRepository
from mist_service.repositories.planning import SqlAlchemyPlanningRepository
from mist_service.services.planning_evolution_service import (
    PlanningEvolutionService,
)


@dataclass(slots=True)
class _PlanningAccess:
    session: AsyncSession

    async def authorise_read(
        self, actor: Actor, team_id: UUID, action: ManagementAction
    ) -> None:
        await authorise_planning_read(self.session, actor, team_id, action)

    async def authorise_preview(
        self, actor: Actor, team_id: UUID, grant_id: UUID
    ) -> None:
        await authorise_planning_preview(self.session, actor, team_id, grant_id)


@dataclass(slots=True)
class _PlanningCapacity:
    session: AsyncSession

    async def capacity(
        self, team_id: UUID, date_from: date, date_to: date
    ) -> PlanningCapacityProjection:
        return await calculate_planning_capacity(
            self.session,
            team_id=team_id,
            date_from=date_from,
            date_to=date_to,
        )


@dataclass(slots=True)
class _PlanningFreshness:
    session: AsyncSession

    async def freshness(self) -> PlanningFreshnessState:
        state = await self.session.get(AnalyticsProjectionState, PROJECTION_NAME)
        return PlanningFreshnessState(
            rebuilding=(state is None or state.health is ProjectionHealth.REBUILDING),
            last_projected_at=state.last_projected_at if state is not None else None,
        )


def planning_evolution_service(session: AsyncSession) -> PlanningEvolutionService:
    """Wire planning use cases to transaction-scoped infrastructure adapters."""
    planning = SqlAlchemyPlanningRepository(session)
    return PlanningEvolutionService(
        access=_PlanningAccess(session),
        board=SqlAlchemyBoardRepository(session),
        queries=planning,
        scenarios=planning,
        capacity=_PlanningCapacity(session),
        freshness=_PlanningFreshness(session),
    )
