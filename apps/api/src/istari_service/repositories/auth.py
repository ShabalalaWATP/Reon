"""SQLAlchemy authentication repository adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.domain import AccountRecord, Actor, SessionRecord
from istari_service.models import Session, User
from istari_service.team_models import TeamMembership


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def actor_from_user(
    user: User,
    organisation_unit_ids: frozenset[UUID] = frozenset(),
) -> Actor:
    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        scope=user.scope,
        organisation_unit_ids=organisation_unit_ids,
    )


def account_from_user(
    user: User,
    organisation_unit_ids: frozenset[UUID] = frozenset(),
) -> AccountRecord:
    return AccountRecord(
        actor=actor_from_user(user, organisation_unit_ids),
        password_hash=user.password_hash,
        is_active=user.is_active,
        failed_login_count=user.failed_login_count,
        locked_until=_as_utc(user.locked_until) if user.locked_until else None,
    )


async def actor_from_user_with_memberships(
    session: AsyncSession,
    user: User,
) -> Actor:
    now = datetime.now(UTC)
    unit_ids = frozenset(
        await session.scalars(
            select(TeamMembership.team_id).where(
                TeamMembership.user_id == user.id,
                TeamMembership.effective_from <= now,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > now,
                ),
            )
        )
    )
    return actor_from_user(user, unit_ids)


class SqlAlchemyAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_account(self, username: str) -> AccountRecord | None:
        user = await self._session.scalar(select(User).where(User.username == username))
        if user is None:
            return None
        return AccountRecord(
            actor=await actor_from_user_with_memberships(self._session, user),
            password_hash=user.password_hash,
            is_active=user.is_active,
            failed_login_count=user.failed_login_count,
            locked_until=_as_utc(user.locked_until) if user.locked_until else None,
        )

    async def record_failure(
        self,
        account: AccountRecord,
        *,
        now: datetime,
        lockout_threshold: int,
        lockout_seconds: int,
    ) -> None:
        next_count = User.failed_login_count + 1
        threshold_reached = next_count >= lockout_threshold
        await self._session.execute(
            update(User)
            .where(
                User.id == account.actor.id,
                User.is_active.is_(True),
                or_(User.locked_until.is_(None), User.locked_until <= now),
            )
            .values(
                failed_login_count=case(
                    (threshold_reached, 0),
                    else_=next_count,
                ),
                locked_until=case(
                    (
                        threshold_reached,
                        now + timedelta(seconds=lockout_seconds),
                    ),
                    else_=None,
                ),
            )
        )

    async def reset_failures(self, account: AccountRecord) -> None:
        user = await self._session.get(User, account.actor.id)
        if user is not None:
            user.failed_login_count = 0
            user.locked_until = None

    async def revoke_user_sessions(self, account: AccountRecord) -> None:
        await self._session.execute(
            update(Session)
            .where(Session.user_id == account.actor.id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

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
            expires_at=expires_at,
        )
        self._session.add(stored)
        await self._session.flush()
        return SessionRecord(
            id=stored.id,
            actor=account.actor,
            csrf_token_hash=stored.csrf_token_hash,
            expires_at=expires_at,
            elevated_until=None,
        )

    async def find_session(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_cutoff: datetime,
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
            or _as_utc(stored.expires_at) <= now
            or _as_utc(stored.last_seen_at) <= idle_cutoff
            or not stored.user.is_active
            or stored.credential_version != stored.user.credential_version
            or (
                stored.user.locked_until is not None
                and _as_utc(stored.user.locked_until) > now
            )
        )
        if invalid:
            if stored.revoked_at is None:
                stored.revoked_at = now
            return None
        idle_window = now - idle_cutoff
        touch_cutoff = now - (idle_window / 2)
        if _as_utc(stored.last_seen_at) <= touch_cutoff:
            stored.last_seen_at = now
        return SessionRecord(
            id=stored.id,
            actor=await actor_from_user_with_memberships(
                self._session,
                stored.user,
            ),
            csrf_token_hash=stored.csrf_token_hash,
            expires_at=_as_utc(stored.expires_at),
            elevated_until=(
                _as_utc(stored.elevated_until) if stored.elevated_until else None
            ),
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

    async def commit_security_state(self) -> None:
        """Durably persist auth defences before an expected request rollback."""

        await self._session.commit()
