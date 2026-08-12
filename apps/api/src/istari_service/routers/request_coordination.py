"""Authenticated coordination endpoints shared by request participants."""

from uuid import UUID

from fastapi import APIRouter

from istari_service.dependencies import DatabaseSession, MutationActor
from istari_service.schemas.coordination import (
    CoordinationMessageCreate,
    CoordinationResult,
    ReturnRequestCreate,
)
from istari_service.services.request_coordination_service import (
    RequestCoordinationService,
)

router = APIRouter(prefix="/requests", tags=["request-coordination"])


@router.post("/{request_id}/coordination", response_model=CoordinationResult)
async def post_coordination(
    request_id: UUID,
    command: CoordinationMessageCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> CoordinationResult:
    event = await RequestCoordinationService(session).post_message(
        actor, request_id, command
    )
    return CoordinationResult(event=event)

@router.post("/{request_id}/return-requests", response_model=CoordinationResult)
async def request_return(
    request_id: UUID,
    command: ReturnRequestCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> CoordinationResult:
    event = await RequestCoordinationService(session).request_return(
        actor, request_id, command
    )
    return CoordinationResult(event=event)
