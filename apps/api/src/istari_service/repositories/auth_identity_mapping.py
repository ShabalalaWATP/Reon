"""Map authentication persistence models into domain identity records."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import AccountRecord, Actor, SessionRecord
from istari_service.models import IdentityContext, Session, User, UserRole
from istari_service.team_models import TeamMembership


def as_utc(value: datetime) -> datetime:
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


def available_contexts(user: User) -> tuple[IdentityContext, ...]:
    if user.role is UserRole.REQUESTER:
        return (IdentityContext.CUSTOMER,)
    if user.role is UserRole.PLATFORM_ADMIN or not user.customer_context_enabled:
        return (IdentityContext.STAFF,)
    return (IdentityContext.STAFF, IdentityContext.CUSTOMER)


def actor_in_context(
    user: User,
    context: IdentityContext,
    organisation_unit_ids: frozenset[UUID],
) -> Actor:
    if context is IdentityContext.CUSTOMER:
        return Actor(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=UserRole.REQUESTER,
            scope="Customer",
            organisation_unit_ids=frozenset(),
        )
    return actor_from_user(user, organisation_unit_ids)


def account_from_user(
    user: User,
    organisation_unit_ids: frozenset[UUID] = frozenset(),
) -> AccountRecord:
    return AccountRecord(
        actor=actor_from_user(user, organisation_unit_ids),
        password_hash=user.password_hash,
        is_active=user.is_active,
        failed_login_count=user.failed_login_count,
        locked_until=as_utc(user.locked_until) if user.locked_until else None,
        customer_context_enabled=user.customer_context_enabled,
    )


async def actor_from_user_with_memberships(session: AsyncSession, user: User) -> Actor:
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


def session_record_from_model(
    stored: Session,
    *,
    organisation_unit_ids: frozenset[UUID],
) -> SessionRecord:
    return SessionRecord(
        id=stored.id,
        actor=actor_in_context(
            stored.user, stored.active_context, organisation_unit_ids
        ),
        csrf_token_hash=stored.csrf_token_hash,
        expires_at=as_utc(stored.expires_at),
        last_seen_at=as_utc(stored.last_seen_at),
        elevated_until=(
            as_utc(stored.elevated_until) if stored.elevated_until else None
        ),
        active_context=stored.active_context,
        available_contexts=available_contexts(stored.user),
        context_version=stored.context_version,
    )
