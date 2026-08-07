"""Manual related-record use cases over a narrow persistence port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import UserRole
from istari_service.schemas.related_records import (
    RelatedRecordCandidate,
    RequestLinkCreate,
    RequestLinkView,
    RequestLinkWorkspace,
)


@dataclass(frozen=True, slots=True)
class RelatedRecordSource:
    request_id: UUID
    version: int


class RelatedRecordRepository(Protocol):
    async def source(
        self,
        work_id: UUID,
        actor: Actor,
        *,
        lock: bool,
    ) -> RelatedRecordSource | None: ...

    async def search(
        self,
        source_id: UUID,
        actor: Actor,
        query: str,
        limit: int,
    ) -> list[RelatedRecordCandidate]: ...

    async def links(self, source_id: UUID) -> list[RequestLinkView]: ...

    async def create(
        self,
        source: RelatedRecordSource,
        actor: Actor,
        command: RequestLinkCreate,
    ) -> RequestLinkWorkspace: ...


class RelatedRecordService:
    def __init__(self, repository: RelatedRecordRepository) -> None:
        self._repository = repository

    async def search(
        self,
        actor: Actor,
        work_id: UUID,
        query: str,
        limit: int,
    ) -> list[RelatedRecordCandidate]:
        source = await self._authorised_source(actor, work_id, lock=False)
        return await self._repository.search(
            source.request_id,
            actor,
            query.strip(),
            limit,
        )

    async def links(self, actor: Actor, work_id: UUID) -> RequestLinkWorkspace:
        source = await self._authorised_source(actor, work_id, lock=False)
        return RequestLinkWorkspace(
            source_version=source.version,
            items=await self._repository.links(source.request_id),
        )

    async def create(
        self,
        actor: Actor,
        work_id: UUID,
        command: RequestLinkCreate,
    ) -> RequestLinkWorkspace:
        source = await self._authorised_source(actor, work_id, lock=True)
        return await self._repository.create(source, actor, command)

    async def _authorised_source(
        self,
        actor: Actor,
        work_id: UUID,
        *,
        lock: bool,
    ) -> RelatedRecordSource:
        if actor.role is not UserRole.INTAKE_TRIAGE:
            raise ObjectNotFound()
        source = await self._repository.source(work_id, actor, lock=lock)
        if source is None:
            raise ObjectNotFound()
        return source
