"""Authenticated organisation and route-scoped tracking routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from istari_service.dependencies import CurrentActor, DatabaseSession
from istari_service.models import RequestStatus
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
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    status_filter: Annotated[list[RequestStatus] | None, Query(alias="status")] = None,
    current_owner: Annotated[
        str | None, Query(alias="currentOwner", min_length=1, max_length=120)
    ] = None,
    route_unit_id: Annotated[UUID | None, Query(alias="routeUnitId")] = None,
    minimum_age_days: Annotated[
        int | None, Query(alias="minimumAgeDays", ge=0, le=3650)
    ] = None,
) -> TrackedRequestList:
    items, next_cursor = await _service(session).page_tracked_requests(
        actor,
        limit=limit,
        cursor=cursor,
        search=search,
        statuses=tuple(status_filter or ()),
        current_owner=current_owner,
        route_unit_id=route_unit_id,
        minimum_age_days=minimum_age_days,
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
    event_limit: Annotated[int, Query(alias="eventLimit", ge=1, le=100)] = 50,
    event_cursor: Annotated[
        str | None, Query(alias="eventCursor", max_length=500)
    ] = None,
) -> TrackedRequestDetail:
    return await _service(session).get_tracked_request_detail(
        actor,
        request_id,
        event_limit=event_limit,
        event_cursor=event_cursor,
    )
