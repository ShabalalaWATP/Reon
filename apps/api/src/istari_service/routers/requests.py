"""Requester-owned service-request HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse

from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
)
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.requests import SqlAlchemyRequestRepository
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestCreate,
    RequestDetail,
    RequestList,
)
from istari_service.services.request_service import RequestService

router = APIRouter(prefix="/requests", tags=["service requests"])


def _service(
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestService:
    return RequestService(
        SqlAlchemyRequestRepository(
            session,
            process_id=settings.camunda_process_id,
            configuration_pins=SqlAlchemyConfigurationPinRepository(session),
        )
    )


@router.get("", response_model=RequestList)
async def list_requests(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestList:
    items = await _service(session, settings).list(actor)
    return RequestList(items=items)


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED)
async def create_request(
    command: RequestCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await _service(session, settings).create(actor, command)


@router.get("/{request_id}", response_model=RequestDetail)
async def get_request(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await _service(session, settings).get(actor, request_id)


@router.post("/{request_id}/feedback", response_model=FeedbackView)
async def submit_feedback(
    request_id: UUID,
    command: FeedbackCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> FeedbackView:
    return await _service(session, settings).add_feedback(
        actor,
        request_id,
        command,
    )


@router.get("/{request_id}/product", response_class=PlainTextResponse)
async def download_product(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> PlainTextResponse:
    filename, text = await _service(session, settings).download_product(
        actor,
        request_id,
    )
    return PlainTextResponse(
        text,
        media_type="text/plain",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
