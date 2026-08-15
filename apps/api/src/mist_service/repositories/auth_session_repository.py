"""Session-token persistence and validation for authentication."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mist_service.domain import AccountRecord, SessionRecord
from mist_service.models import IdentityContext, Session, User, UserRole
from mist_service.repositories.auth_identity_mapping import (
    actor_from_user_with_memberships,
    as_utc,
    available_contexts,
    session_record_from_model,
)


class SqlAlchemyAuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self,
        account: AccountRecord,
        *,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        user = await self._session.get(User, account.actor.id)
        if user is None or not user.is_active:
            raise LookupError("account no longer available")
        stored = Session(
            user_id=user.id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            credential_version=user.credential_version,
            active_context=(
                IdentityContext.CUSTOMER
                if user.role is UserRole.REQUESTER
                else IdentityContext.STAFF
            ),
            expires_at=expires_at,
        )
        self._session.add(stored)
        await self._session.flush()
        stored.user = user
        return session_record_from_model(
            stored, organisation_unit_ids=account.actor.organisation_unit_ids
        )

    async def find_session(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_cutoff: datetime,
        touch: bool = False,
    ) -> SessionRecord | None:
        stored = await self._session.scalar(
            select(Session)
            .options(selectinload(Session.user))
            .where(Session.token_hash == token_hash)
        )
        if stored is None:
            return None
        invalid = (
            stored.revoked_at is not None
            or as_utc(stored.expires_at) <= now
            or as_utc(stored.last_seen_at) <= idle_cutoff
            or not stored.user.is_active
            or stored.credential_version != stored.user.credential_version
            or (
                stored.user.locked_until is not None
                and as_utc(stored.user.locked_until) > now
            )
        )
        if invalid:
            if stored.revoked_at is None:
                stored.revoked_at = now
            return None
        idle_window = now - idle_cutoff
        touch_cutoff = now - (idle_window / 2)
        if touch and as_utc(stored.last_seen_at) <= touch_cutoff:
            stored.last_seen_at = now
        contexts = available_contexts(stored.user)
        if (
            stored.user.role is UserRole.REQUESTER
            and stored.active_context is IdentityContext.STAFF
        ):
            stored.active_context = IdentityContext.CUSTOMER
        if stored.active_context not in contexts:
            stored.revoked_at = now
            return None
        unit_ids: frozenset[UUID] = frozenset()
        if stored.active_context is IdentityContext.STAFF:
            unit_ids = (
                await actor_from_user_with_memberships(self._session, stored.user)
            ).organisation_unit_ids
        return session_record_from_model(stored, organisation_unit_ids=unit_ids)

    async def touch_session(self, session_id: UUID, *, now: datetime) -> None:
        await self._session.execute(
            update(Session)
            .where(Session.id == session_id, Session.revoked_at.is_(None))
            .values(last_seen_at=now)
        )

    async def set_elevation(self, session_id: UUID, until: datetime) -> None:
        result = await self._session.execute(
            update(Session)
            .where(Session.id == session_id, Session.revoked_at.is_(None))
            .values(elevated_until=until)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise LookupError("session no longer available")

    async def revoke_session(self, session_id: UUID) -> None:
        stored = await self._session.get(Session, session_id)
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)

    async def rotate_csrf(self, session_id: UUID, csrf_token_hash: str) -> None:
        stored = await self._session.get(Session, session_id)
        if stored is None or stored.revoked_at is not None:
            raise LookupError("session no longer available")
        stored.csrf_token_hash = csrf_token_hash
