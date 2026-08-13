"""Organisation reference data and constrained tracking use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.schemas.organisation import (
    OrganisationUnitView,
    TrackedRequest,
    TrackedRequestDetail,
)

TRACKING_ROLES = {
    UserRole.INTAKE_TRIAGE,
    UserRole.SERVICE_COORDINATION,
    UserRole.OPERATIONS_ALLOCATION,
}


class OrganisationRepository(Protocol):
    async def list_units(self) -> list[OrganisationUnitView]: ...

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
    ) -> tuple[list[TrackedRequest], str | None]: ...

    async def get_tracked_request_detail(
        self,
        actor: Actor,
        request_id: UUID,
        *,
        event_limit: int = 50,
        event_cursor: str | None = None,
    ) -> TrackedRequestDetail | None: ...


class OrganisationService:
    def __init__(self, repository: OrganisationRepository) -> None:
        self._repository = repository

    async def list_units(self, actor: Actor) -> list[OrganisationUnitView]:
        if actor.role is UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._repository.list_units()

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
        if actor.role not in TRACKING_ROLES:
            raise ObjectNotFound()
        return await self._repository.page_tracked_requests(
            actor,
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
    ) -> TrackedRequestDetail:
        if actor.role not in TRACKING_ROLES:
            raise ObjectNotFound()
        detail = await self._repository.get_tracked_request_detail(
            actor,
            request_id,
            event_limit=event_limit,
            event_cursor=event_cursor,
        )
        if detail is None:
            raise ObjectNotFound()
        return detail
