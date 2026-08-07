"""Authenticated exact-team workspace routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from istari_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from istari_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.team_workspaces import (
    EligibleRosterAnalystList,
    EndMembershipCommand,
    RosterCommand,
    TeamActivityList,
    TeamPeople,
    TeamWorkspaceList,
    TeamWorkspaceOverview,
    TransferCommand,
)
from istari_service.services.team_workspace_service import TeamWorkspaceService

router = APIRouter(prefix="/team-workspaces", tags=["team-workspaces"])


def _service(session: DatabaseSession) -> TeamWorkspaceService:
    return TeamWorkspaceService(
        SqlAlchemyTeamWorkspaceRepository(session),
        SqlAlchemyTeamMembershipRepository(session),
    )


@router.get("", response_model=TeamWorkspaceList)
async def list_team_workspaces(
    actor: CurrentActor, session: DatabaseSession
) -> TeamWorkspaceList:
    return TeamWorkspaceList(items=await _service(session).list_access(actor))


@router.get("/{team_id}", response_model=TeamWorkspaceOverview)
async def get_team_workspace(
    team_id: UUID, actor: CurrentActor, session: DatabaseSession
) -> TeamWorkspaceOverview:
    return await _service(session).overview(actor, team_id)


@router.get("/{team_id}/people", response_model=TeamPeople)
async def get_team_people(
    team_id: UUID, actor: CurrentActor, session: DatabaseSession
) -> TeamPeople:
    return TeamPeople(items=await _service(session).people(actor, team_id))


@router.get("/{team_id}/eligible-analysts", response_model=EligibleRosterAnalystList)
async def get_eligible_analysts(
    team_id: UUID,
    grant_id: Annotated[UUID, Query(alias="grantId")],
    actor: CurrentActor,
    session: DatabaseSession,
) -> EligibleRosterAnalystList:
    return EligibleRosterAnalystList(
        items=await _service(session).eligible_analysts(actor, team_id, grant_id)
    )


@router.get("/{team_id}/activity", response_model=TeamActivityList)
async def get_team_activity(
    team_id: UUID, actor: CurrentActor, session: DatabaseSession
) -> TeamActivityList:
    return TeamActivityList(items=await _service(session).activity(actor, team_id))


@router.post("/{team_id}/memberships", response_model=TeamPeople)
async def add_team_member(
    team_id: UUID,
    command: RosterCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> TeamPeople:
    return TeamPeople(items=await _service(session).add(actor, team_id, command))


@router.post("/{team_id}/transfers", response_model=TeamPeople)
async def schedule_team_transfer(
    team_id: UUID,
    command: TransferCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> TeamPeople:
    return TeamPeople(items=await _service(session).transfer(actor, team_id, command))


@router.post("/{team_id}/memberships/{membership_id}/end", response_model=TeamPeople)
async def end_team_membership(
    team_id: UUID,
    membership_id: UUID,
    command: EndMembershipCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> TeamPeople:
    return TeamPeople(
        items=await _service(session).end(actor, team_id, membership_id, command)
    )
