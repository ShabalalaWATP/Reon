"""Compatibility facade for SQLAlchemy authentication persistence adapters."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.compliance_models import SecurityEvent
from mist_service.domain import AccountRecord, SessionRecord
from mist_service.models import IdentityContext
from mist_service.repositories.auth_account_repository import (
    SqlAlchemyAuthAccountRepository,
)
from mist_service.repositories.auth_context_repository import (
    SqlAlchemyAuthContextRepository,
)
from mist_service.repositories.auth_identity_mapping import (
    account_from_user,
    actor_from_user,
    actor_from_user_with_memberships,
    actor_in_context,
    available_contexts,
)
from mist_service.repositories.auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

__all__ = [
    "SqlAlchemyAuthRepository",
    "account_from_user",
    "actor_from_user",
    "actor_from_user_with_memberships",
    "actor_in_context",
    "available_contexts",
]


class SqlAlchemyAuthRepository:
    """Expose the legacy auth port while delegating to cohesive adapters."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = SqlAlchemyAuthAccountRepository(session)
        self._sessions = SqlAlchemyAuthSessionRepository(session)
        self._contexts = SqlAlchemyAuthContextRepository(session)

    async def find_account(self, username: str) -> AccountRecord | None:
        return await self._accounts.find_account(username)

    async def record_step_up_failure(
        self,
        account: AccountRecord,
        *,
        now: datetime,
        lockout_threshold: int,
        lockout_seconds: int,
    ) -> None:
        await self._accounts.record_step_up_failure(
            account,
            now=now,
            lockout_threshold=lockout_threshold,
            lockout_seconds=lockout_seconds,
        )

    async def reset_failures(self, account: AccountRecord) -> None:
        await self._accounts.reset_failures(account)

    async def revoke_user_sessions(self, account: AccountRecord) -> None:
        await self._accounts.revoke_user_sessions(account)

    async def create_session(
        self,
        account: AccountRecord,
        *,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        return await self._sessions.create_session(
            account,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
        )

    async def find_session(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_cutoff: datetime,
        touch: bool = False,
    ) -> SessionRecord | None:
        return await self._sessions.find_session(
            token_hash, now=now, idle_cutoff=idle_cutoff, touch=touch
        )

    async def lock_mutation_context(
        self, session_id: UUID, *, expected_context_version: int
    ) -> bool:
        return await self._contexts.lock_mutation_context(
            session_id, expected_context_version=expected_context_version
        )

    async def switch_context(
        self,
        session_id: UUID,
        *,
        context: IdentityContext,
        expected_context_version: int,
        token_hash: str,
        csrf_token_hash: str,
    ) -> SessionRecord:
        return await self._contexts.switch_context(
            session_id,
            context=context,
            expected_context_version=expected_context_version,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
        )

    async def touch_session(self, session_id: UUID, *, now: datetime) -> None:
        await self._sessions.touch_session(session_id, now=now)

    async def set_elevation(
        self,
        session_id: UUID,
        until: datetime,
        *,
        token_hash: str,
        csrf_token_hash: str,
    ) -> None:
        await self._sessions.set_elevation(
            session_id,
            until,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
        )

    async def revoke_session(self, session_id: UUID) -> None:
        await self._sessions.revoke_session(session_id)

    async def rotate_csrf(self, session_id: UUID, csrf_token_hash: str) -> None:
        await self._sessions.rotate_csrf(session_id, csrf_token_hash)

    async def commit_security_state(
        self, security_event: SecurityEvent | None = None
    ) -> None:
        if security_event is not None:
            self._session.add(security_event)
        await self._session.commit()
