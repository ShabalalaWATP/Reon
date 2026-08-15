"""Pessimistically locked identity-context session persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mist_service.domain import SessionRecord
from mist_service.models import IdentityContext, Session
from mist_service.repositories.auth_identity_mapping import (
    actor_from_user_with_memberships,
    available_contexts,
    session_record_from_model,
)


class SqlAlchemyAuthContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_mutation_context(
        self, session_id: UUID, *, expected_context_version: int
    ) -> bool:
        """Fence a mutation against concurrent context switches and revocation."""

        stored_id = await self._session.scalar(
            select(Session.id)
            .where(
                Session.id == session_id,
                Session.revoked_at.is_(None),
                Session.context_version == expected_context_version,
            )
            .with_for_update()
        )
        return stored_id is not None

    async def switch_context(
        self,
        session_id: UUID,
        *,
        context: IdentityContext,
        expected_context_version: int,
        token_hash: str,
        csrf_token_hash: str,
    ) -> SessionRecord:
        stored = await self._session.scalar(
            select(Session)
            .options(selectinload(Session.user))
            .where(
                Session.id == session_id,
                Session.revoked_at.is_(None),
                Session.context_version == expected_context_version,
            )
            .with_for_update()
        )
        if stored is None or context not in available_contexts(stored.user):
            raise PermissionError("identity context is unavailable")
        stored.active_context = context
        stored.context_version += 1
        stored.token_hash = token_hash
        stored.csrf_token_hash = csrf_token_hash
        stored.elevated_until = None
        await self._session.flush()
        staff_actor = await actor_from_user_with_memberships(self._session, stored.user)
        return session_record_from_model(
            stored, organisation_unit_ids=staff_actor.organisation_unit_ids
        )
