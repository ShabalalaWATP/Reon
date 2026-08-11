"""Customer draft use cases independent of HTTP and persistence details."""

from __future__ import annotations

import builtins
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import UserRole
from istari_service.schemas.drafts import (
    RequestDraftCreate,
    RequestDraftSubmit,
    RequestDraftUpdate,
    RequestDraftView,
)
from istari_service.schemas.requests import RequestDetail


class DraftRepository(Protocol):
    async def list_for_requester(
        self, requester_id: UUID
    ) -> list[RequestDraftView]: ...
    async def page_for_requester(
        self,
        requester_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[RequestDraftView], str | None]: ...
    async def get(
        self, draft_id: UUID, requester_id: UUID
    ) -> RequestDraftView | None: ...
    async def create(
        self, actor: Actor, command: RequestDraftCreate
    ) -> RequestDraftView: ...
    async def update(
        self, draft_id: UUID, actor: Actor, command: RequestDraftUpdate
    ) -> RequestDraftView: ...
    async def delete(
        self, draft_id: UUID, requester_id: UUID, expected_version: int
    ) -> None: ...
    async def submit(
        self, draft_id: UUID, actor: Actor, command: RequestDraftSubmit
    ) -> RequestDetail: ...


class DraftService:
    def __init__(self, repository: DraftRepository) -> None:
        self._repository = repository

    @staticmethod
    def _require_customer(actor: Actor) -> None:
        if actor.role is not UserRole.REQUESTER:
            raise ObjectNotFound()

    async def list(self, actor: Actor) -> list[RequestDraftView]:
        self._require_customer(actor)
        return await self._repository.list_for_requester(actor.id)

    async def list_page(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[builtins.list[RequestDraftView], str | None]:
        self._require_customer(actor)
        return await self._repository.page_for_requester(
            actor.id, limit=limit, cursor=cursor
        )

    async def get(self, actor: Actor, draft_id: UUID) -> RequestDraftView:
        self._require_customer(actor)
        draft = await self._repository.get(draft_id, actor.id)
        if draft is None:
            raise ObjectNotFound()
        return draft

    async def create(
        self, actor: Actor, command: RequestDraftCreate
    ) -> RequestDraftView:
        self._require_customer(actor)
        return await self._repository.create(actor, command)

    async def update(
        self, actor: Actor, draft_id: UUID, command: RequestDraftUpdate
    ) -> RequestDraftView:
        self._require_customer(actor)
        return await self._repository.update(
            actor=actor, draft_id=draft_id, command=command
        )

    async def delete(self, actor: Actor, draft_id: UUID, expected_version: int) -> None:
        self._require_customer(actor)
        await self._repository.delete(draft_id, actor.id, expected_version)

    async def submit(
        self, actor: Actor, draft_id: UUID, command: RequestDraftSubmit
    ) -> RequestDetail:
        self._require_customer(actor)
        return await self._repository.submit(draft_id, actor, command)
