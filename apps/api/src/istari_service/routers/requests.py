"""Requester-owned service-request HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status
from fastapi.responses import PlainTextResponse

from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
)
from istari_service.request_composition import build_request_service
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestCancel,
    RequestCreate,
    RequestDetail,
    RequestList,
)

router = APIRouter(prefix="/requests", tags=["service requests"])


@router.get("", response_model=RequestList)
async def list_requests(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> RequestList:
    items, next_cursor = await build_request_service(session, settings).list_page(
        actor, limit=limit, cursor=cursor
    )
    return RequestList(items=items, next_cursor=next_cursor)


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED)
async def create_request(
    command: RequestCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await build_request_service(session, settings).create(actor, command)


@router.get("/{request_id}", response_model=RequestDetail)
async def get_request(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
    event_limit: int = Query(default=50, alias="eventLimit", ge=1, le=100),
    event_cursor: str | None = Query(default=None, alias="eventCursor", max_length=500),
) -> RequestDetail:
    return await build_request_service(session, settings).get_page(
        actor,
        request_id,
        event_limit=event_limit,
        event_cursor=event_cursor,
    )


@router.post("/{request_id}/feedback", response_model=FeedbackView)
async def submit_feedback(
    request_id: UUID,
    command: FeedbackCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> FeedbackView:
    return await build_request_service(session, settings).add_feedback(
        actor,
        request_id,
        command,
    )


@router.post("/{request_id}/cancel", response_model=RequestDetail)
async def cancel_request(
    request_id: UUID,
    command: RequestCancel,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await build_request_service(session, settings).cancel(
        actor, request_id, command
    )


@router.get("/{request_id}/product", response_class=PlainTextResponse)
async def download_product(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> PlainTextResponse:
    filename, text = await build_request_service(session, settings).download_product(
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
