"""Authenticated organisation and route-scoped tracking routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from istari_service.dependencies import CurrentActor, DatabaseSession
from istari_service.repositories.organisation import SqlAlchemyOrganisationRepository
from istari_service.schemas.organisation import (
    OrganisationUnitList,
    TrackedRequestDetail,
    TrackedRequestList,
)
from istari_service.services.organisation_service import OrganisationService

router = APIRouter(tags=["organisation"])


def _service(session: DatabaseSession) -> OrganisationService:
    return OrganisationService(SqlAlchemyOrganisationRepository(session))


@router.get("/organisation/units", response_model=OrganisationUnitList)
async def list_organisation_units(
    actor: CurrentActor,
    session: DatabaseSession,
) -> OrganisationUnitList:
    return OrganisationUnitList(items=await _service(session).list_units(actor))


@router.get("/tracked-requests", response_model=TrackedRequestList)
async def list_tracked_requests(
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> TrackedRequestList:
    items, next_cursor = await _service(session).page_tracked_requests(
        actor, limit=limit, cursor=cursor
    )
    return TrackedRequestList(
        items=items,
        next_cursor=next_cursor,
    )


@router.get("/tracked-requests/{request_id}", response_model=TrackedRequestDetail)
async def get_tracked_request_detail(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> TrackedRequestDetail:
    return await _service(session).get_tracked_request_detail(actor, request_id)
