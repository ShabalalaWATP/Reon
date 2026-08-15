"""Persistence adapter methods for prepared work-command intents."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor, WorkRecord
from mist_service.repositories.work_intents import (
    prepare_claim_intent,
    prepare_completion_intent,
)
from mist_service.schemas.work import CompletionPayload


class WorkIntentRepositoryMixin:
    _session: AsyncSession
    _managed_products_enabled: bool

    async def prepare_claim(self, work: WorkRecord, actor: Actor) -> UUID:
        return await prepare_claim_intent(self._session, work, actor)

    async def prepare_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
    ) -> UUID:
        return await prepare_completion_intent(
            self._session,
            work,
            actor,
            payload,
            managed_products_enabled=self._managed_products_enabled,
        )

    async def commit_intent(self) -> None:
        await self._session.commit()

    def expire_state(self) -> None:
        self._session.expire_all()
