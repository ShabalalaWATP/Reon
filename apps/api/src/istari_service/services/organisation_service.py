"""Organisation reference data and constrained tracking use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import UserRole
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
    ) -> tuple[list[TrackedRequest], str | None]: ...

    async def get_tracked_request_detail(
        self, actor: Actor, request_id: UUID
    ) -> TrackedRequestDetail | None: ...


class OrganisationService:
    def __init__(self, repository: OrganisationRepository) -> None:
        self._repository = repository

    async def list_units(self, _actor: Actor) -> list[OrganisationUnitView]:
        return await self._repository.list_units()

    async def page_tracked_requests(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[TrackedRequest], str | None]:
        if actor.role not in TRACKING_ROLES:
            raise ObjectNotFound()
        return await self._repository.page_tracked_requests(
            actor, limit=limit, cursor=cursor
        )

    async def get_tracked_request_detail(
        self,
        actor: Actor,
        request_id: UUID,
    ) -> TrackedRequestDetail:
        if actor.role not in TRACKING_ROLES:
            raise ObjectNotFound()
        detail = await self._repository.get_tracked_request_detail(actor, request_id)
        if detail is None:
            raise ObjectNotFound()
        return detail
