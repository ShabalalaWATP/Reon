"""Account and login-failure persistence for authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import AccountRecord
from istari_service.models import Session, User
from istari_service.repositories.auth_identity_mapping import (
    actor_from_user_with_memberships,
    as_utc,
)


class SqlAlchemyAuthAccountRepository:
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
            locked_until=as_utc(user.locked_until) if user.locked_until else None,
            customer_context_enabled=user.customer_context_enabled,
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
            .where(User.id == account.actor.id, User.is_active.is_(True))
            .values(
                failed_login_count=case((threshold_reached, 0), else_=next_count),
                locked_until=case(
                    (threshold_reached, now + timedelta(seconds=lockout_seconds)),
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
