"""Customer-owned private request-draft routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from mist_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
)
from mist_service.request_composition import build_draft_service
from mist_service.schemas.drafts import (
    RequestDraftCreate,
    RequestDraftList,
    RequestDraftSubmit,
    RequestDraftUpdate,
    RequestDraftView,
)
from mist_service.schemas.requests import RequestDetail

router = APIRouter(prefix="/request-drafts", tags=["request drafts"])


@router.get("", response_model=RequestDraftList)
async def list_drafts(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> RequestDraftList:
    items, next_cursor = await build_draft_service(session, settings).list_page(
        actor, limit=limit, cursor=cursor
    )
    return RequestDraftList(items=items, next_cursor=next_cursor)


@router.post("", response_model=RequestDraftView, status_code=status.HTTP_201_CREATED)
async def create_draft(
    command: RequestDraftCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await build_draft_service(session, settings).create(actor, command)


@router.get("/{draft_id}", response_model=RequestDraftView)
async def get_draft(
    draft_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await build_draft_service(session, settings).get(actor, draft_id)


@router.patch("/{draft_id}", response_model=RequestDraftView)
async def update_draft(
    draft_id: UUID,
    command: RequestDraftUpdate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await build_draft_service(session, settings).update(actor, draft_id, command)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    expected_version: Annotated[int, Query(alias="expectedVersion", ge=1)],
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> Response:
    await build_draft_service(session, settings).delete(
        actor, draft_id, expected_version
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{draft_id}/submit", response_model=RequestDetail)
async def submit_draft(
    draft_id: UUID,
    command: RequestDraftSubmit,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await build_draft_service(session, settings).submit(actor, draft_id, command)
