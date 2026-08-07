"""Customer-owned private request-draft routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
)
from istari_service.repositories.drafts import SqlAlchemyDraftRepository
from istari_service.schemas.drafts import (
    RequestDraftCreate,
    RequestDraftList,
    RequestDraftSubmit,
    RequestDraftUpdate,
    RequestDraftView,
)
from istari_service.schemas.requests import RequestDetail
from istari_service.services.draft_service import DraftService

router = APIRouter(prefix="/request-drafts", tags=["request drafts"])


def _service(session: DatabaseSession, settings: AppSettings) -> DraftService:
    return DraftService(
        SqlAlchemyDraftRepository(session, process_id=settings.camunda_process_id)
    )


@router.get("", response_model=RequestDraftList)
async def list_drafts(
    actor: CurrentActor, session: DatabaseSession, settings: AppSettings
) -> RequestDraftList:
    return RequestDraftList(items=await _service(session, settings).list(actor))


@router.post("", response_model=RequestDraftView, status_code=status.HTTP_201_CREATED)
async def create_draft(
    command: RequestDraftCreate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await _service(session, settings).create(actor, command)


@router.get("/{draft_id}", response_model=RequestDraftView)
async def get_draft(
    draft_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await _service(session, settings).get(actor, draft_id)


@router.patch("/{draft_id}", response_model=RequestDraftView)
async def update_draft(
    draft_id: UUID,
    command: RequestDraftUpdate,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDraftView:
    return await _service(session, settings).update(actor, draft_id, command)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    expected_version: Annotated[int, Query(alias="expectedVersion", ge=1)],
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> Response:
    await _service(session, settings).delete(actor, draft_id, expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{draft_id}/submit", response_model=RequestDetail)
async def submit_draft(
    draft_id: UUID,
    command: RequestDraftSubmit,
    actor: MutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> RequestDetail:
    return await _service(session, settings).submit(actor, draft_id, command)
