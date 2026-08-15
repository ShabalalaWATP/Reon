"""Exact-team advisory planning enhancement routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from mist_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from mist_service.planning_evolution_composition import planning_evolution_service
from mist_service.schemas.planning import (
    CapacityScenarioCommand,
    CapacityScenarioList,
    CapacityScenarioPreview,
    PackageTemplateList,
    PlanningCockpit,
)

router = APIRouter(tags=["team-planning"])


@router.get("/{team_id}/planning/cockpit", response_model=PlanningCockpit)
async def get_planning_cockpit(
    team_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> PlanningCockpit:
    return await planning_evolution_service(session).cockpit(actor, team_id)


@router.get("/{team_id}/planning/templates", response_model=PackageTemplateList)
async def list_package_templates(
    team_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> PackageTemplateList:
    return await planning_evolution_service(session).templates(actor, team_id)


@router.get("/{team_id}/planning/scenarios", response_model=CapacityScenarioList)
async def list_capacity_scenarios(
    team_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> CapacityScenarioList:
    return await planning_evolution_service(session).scenarios(actor, team_id)


@router.post(
    "/{team_id}/planning/scenarios/preview",
    response_model=CapacityScenarioPreview,
)
async def preview_capacity_scenario(
    team_id: UUID,
    command: CapacityScenarioCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> CapacityScenarioPreview:
    return await planning_evolution_service(session).preview_scenario(
        actor, team_id, command
    )
