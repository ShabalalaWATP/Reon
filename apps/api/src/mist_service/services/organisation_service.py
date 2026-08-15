"""Organisation reference data and constrained tracking use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound
from mist_service.models import RequestStatus, UserRole
from mist_service.schemas.organisation import (
    OrganisationUnitView,
    TrackedRequest,
    TrackedRequestDetail,
)

TRACKING_ROLES = {
    UserRole.INTAKE_TRIAGE,
    UserRole.SERVICE_COORDINATION,
    UserRole.OPERATIONS_ALLOCATION,
}


class OrganisationReferenceRepository(Protocol):
    async def list_units(
        self, *, include_qc_support: bool = False
    ) -> list[OrganisationUnitView]: ...


class OrganisationTrackingRepository(Protocol):
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
    def __init__(
        self,
        reference_repository: OrganisationReferenceRepository,
        tracking_repository: OrganisationTrackingRepository,
    ) -> None:
        self._reference_repository = reference_repository
        self._tracking_repository = tracking_repository

    async def list_units(self, actor: Actor) -> list[OrganisationUnitView]:
        if actor.role is UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._reference_repository.list_units(
            include_qc_support=actor.role is UserRole.PLATFORM_ADMIN
        )

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
        return await self._tracking_repository.page_tracked_requests(
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
        detail = await self._tracking_repository.get_tracked_request_detail(
            actor,
            request_id,
            event_limit=event_limit,
            event_cursor=event_cursor,
        )
        if detail is None:
            raise ObjectNotFound()
        return detail
