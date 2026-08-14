"""SQLAlchemy adapter for exact-route tracking projections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.repositories.organisation_tracking import (
    tracked_request_detail,
    tracked_requests,
)
from istari_service.repositories.route_access import route_membership_condition
from istari_service.schemas.organisation import TrackedRequest, TrackedRequestDetail


class SqlAlchemyOrganisationTrackingRepository:
    """Read route-scoped tracking data without coupling reference-data access."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def page_tracked_requests(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
        search: str | None = None,
        statuses: tuple[RequestStatus, ...] = (),
        current_owner: str | None = None,
        route_unit_id: UUID | None = None,
        minimum_age_days: int | None = None,
    ) -> tuple[list[TrackedRequest], str | None]:
        membership = route_membership_condition(actor)
        if membership is None:
            return [], None
        membership = and_(membership, ServiceRequest.requester_id != actor.id)
        return await tracked_requests(
            self._session,
            membership,
            limit=limit,
            cursor=cursor,
            search=search,
            statuses=statuses,
            current_owner=current_owner,
            route_unit_id=route_unit_id,
            minimum_age_days=minimum_age_days,
        )

    async def get_tracked_request_detail(
        self,
        actor: Actor,
        request_id: UUID,
        *,
        event_limit: int = 50,
        event_cursor: str | None = None,
    ) -> TrackedRequestDetail | None:
        membership = route_membership_condition(actor)
        if membership is None:
            return None
        membership = and_(membership, ServiceRequest.requester_id != actor.id)
        return await tracked_request_detail(
            self._session,
            membership,
            request_id,
            event_limit=event_limit,
            event_cursor=event_cursor,
        )
