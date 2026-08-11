"""Authenticated workspace collaboration routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from istari_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.repositories.workspace_collaboration import (
    WorkspaceCollaborationRepository,
)
from istari_service.schemas.workspace_collaboration import (
    WorkspaceRecordCreate,
    WorkspaceRecordList,
    WorkspaceRecordResolve,
)
from istari_service.services.workspace_collaboration_service import (
    WorkspaceCollaborationService,
)

router = APIRouter(prefix="/team-workspaces", tags=["workspace-collaboration"])


def _service(session: DatabaseSession) -> WorkspaceCollaborationService:
    return WorkspaceCollaborationService(
        SqlAlchemyTeamWorkspaceRepository(session),
        WorkspaceCollaborationRepository(session),
    )


@router.get("/{unit_id}/records", response_model=WorkspaceRecordList)
async def list_records(
    unit_id: UUID, actor: CurrentActor, session: DatabaseSession
) -> WorkspaceRecordList:
    return WorkspaceRecordList(items=await _service(session).list(actor, unit_id))


@router.post("/{unit_id}/records", response_model=WorkspaceRecordList)
async def create_record(
    unit_id: UUID,
    command: WorkspaceRecordCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkspaceRecordList:
    return WorkspaceRecordList(
        items=await _service(session).create(actor, unit_id, command)
    )


@router.post(
    "/{unit_id}/records/{record_id}/resolve", response_model=WorkspaceRecordList
)
async def resolve_record(
    unit_id: UUID,
    record_id: UUID,
    command: WorkspaceRecordResolve,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkspaceRecordList:
    return WorkspaceRecordList(
        items=await _service(session).resolve(actor, unit_id, record_id, command)
    )
