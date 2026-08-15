"""Exact-team Manager task hastener HTTP boundary."""

from uuid import UUID

from fastapi import APIRouter

from mist_service.action_notification_composition import task_hastener_service
from mist_service.dependencies import DatabaseSession, StaffMutationActor
from mist_service.schemas.task_hasteners import (
    TaskHastenerCommand,
    TaskHastenerResult,
)

router = APIRouter(prefix="/team-workspaces", tags=["task-hasteners"])


@router.post(
    "/{team_id}/requests/{request_id}/hasteners",
    response_model=TaskHastenerResult,
)
async def send_task_hastener(
    team_id: UUID,
    request_id: UUID,
    command: TaskHastenerCommand,
    actor: StaffMutationActor,
    session: DatabaseSession,
) -> TaskHastenerResult:
    return await task_hastener_service(session).send(
        actor, team_id, request_id, command
    )
