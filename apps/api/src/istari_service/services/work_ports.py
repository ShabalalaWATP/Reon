"""Application ports consumed by human work-item use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor, WorkRecord
from istari_service.schemas.organisation import RoutingOptionsWorkspace
from istari_service.schemas.requests import RequestDetail
from istari_service.schemas.work import CompletionPayload
from istari_service.work_types import WorkBundle


class WorkRepository(Protocol):
    async def list_for_actor(self, actor: Actor) -> list[WorkBundle]: ...

    async def page_for_actor(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
        unit_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> tuple[list[WorkBundle], str | None]: ...

    async def get(
        self,
        work_id: UUID,
        actor: Actor | None = None,
    ) -> WorkBundle | None: ...

    async def find_specialist(
        self,
        user_id: UUID,
        *,
        delivery_team_id: UUID | None = None,
    ) -> Actor | None: ...

    async def list_active_specialists(
        self,
        delivery_team: str,
        *,
        delivery_team_id: UUID | None = None,
    ) -> list[Actor]: ...

    async def routing_options(
        self,
        work: WorkRecord,
    ) -> RoutingOptionsWorkspace: ...

    async def prepare_claim(self, work: WorkRecord, actor: Actor) -> UUID: ...

    async def prepare_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
    ) -> UUID: ...

    async def commit_intent(self) -> None: ...

    def expire_state(self) -> None: ...

    async def request_detail(self, request_id: UUID) -> RequestDetail: ...


class CommandDispatcher(Protocol):
    async def dispatch(self, outbox_id: UUID) -> bool: ...
