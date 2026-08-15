"""Legal-hold-aware de-identification for inactive identities."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from mist_service.models import User
from mist_service.retention_targets import not_held


class IdentityRetentionPolicy(Protocol):
    @property
    def identity_days(self) -> int: ...

    @property
    def batch_size(self) -> int: ...


def identity_condition(
    policy: IdentityRetentionPolicy, now: datetime
) -> ColumnElement[bool]:
    return cast(
        ColumnElement[bool],
        User.is_active.is_(False)
        & (User.updated_at <= now - timedelta(days=int(policy.identity_days)))
        & ~User.username.like("disposed-%@invalid")
        & not_held("IDENTITY", User.id),
    )


async def anonymise_identities(
    session: AsyncSession, policy: IdentityRetentionPolicy, now: datetime
) -> int:
    ids = list(
        await session.scalars(
            select(User.id)
            .where(identity_condition(policy, now))
            .order_by(User.id)
            .limit(int(policy.batch_size))
        )
    )
    affected = 0
    for user_id in ids:
        marker = user_id.hex
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(User)
                .where(User.id == user_id, identity_condition(policy, now))
                .values(
                    username=f"disposed-{marker}@invalid",
                    email=f"disposed-{marker}@invalid",
                    display_name="Disposed identity",
                    password_hash=_disposed_password_marker(),
                    scope="disposed",
                    profile_team=None,
                    rank_or_grade=None,
                    service_number=None,
                    additional_information=None,
                    skills=[],
                    assistance_email_hash=None,
                    assistance_email_key_id=None,
                )
            ),
        )
        affected += int(result.rowcount or 0)
    return affected


def _disposed_password_marker() -> str:
    return "DISPOSED_ACCOUNT_NO_LOGIN_HASH"
