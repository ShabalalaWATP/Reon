"""Exact-team Manager task hastener HTTP boundary."""

from uuid import UUID

from fastapi import APIRouter

from istari_service.dependencies import DatabaseSession, MutationActor
from istari_service.repositories.task_hasteners import (
    SqlAlchemyTaskHastenerRepository,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.task_hasteners import (
    TaskHastenerCommand,
    TaskHastenerResult,
)
from istari_service.services.task_hastener_service import TaskHastenerService

router = APIRouter(prefix="/team-workspaces", tags=["task-hasteners"])


@router.post(
    "/{team_id}/requests/{request_id}/hasteners",
    response_model=TaskHastenerResult,
)
async def send_task_hastener(
    team_id: UUID,
    request_id: UUID,
    command: TaskHastenerCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> TaskHastenerResult:
    service = TaskHastenerService(
        SqlAlchemyTaskHastenerRepository(session),
        SqlAlchemyTeamWorkspaceRepository(session),
    )
    return await service.send(actor, team_id, request_id, command)
