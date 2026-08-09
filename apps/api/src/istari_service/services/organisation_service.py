"""Organisation reference data and constrained tracking use cases."""

from __future__ import annotations

from typing import Protocol

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import UserRole
from istari_service.schemas.organisation import OrganisationUnitView, TrackedRequest

TRACKING_ROLES = {
    UserRole.INTAKE_TRIAGE,
    UserRole.SERVICE_COORDINATION,
    UserRole.OPERATIONS_ALLOCATION,
}


class OrganisationRepository(Protocol):
    async def list_units(self) -> list[OrganisationUnitView]: ...

    async def list_tracked_requests(self, actor: Actor) -> list[TrackedRequest]: ...

    async def page_tracked_requests(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[TrackedRequest], str | None]: ...


class OrganisationService:
    def __init__(self, repository: OrganisationRepository) -> None:
        self._repository = repository

    async def list_units(self, _actor: Actor) -> list[OrganisationUnitView]:
        return await self._repository.list_units()

    async def list_tracked_requests(self, actor: Actor) -> list[TrackedRequest]:
        if actor.role not in TRACKING_ROLES:
            raise ObjectNotFound()
        return await self._repository.list_tracked_requests(actor)

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
