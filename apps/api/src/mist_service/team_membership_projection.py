"""Projection refreshes after effective organisation membership changes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import Session, User
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    UserOrganisationMembership,
)
from mist_service.repositories.admin import SqlAlchemyAdminRepository
from mist_service.team_models import TeamMembership


async def refresh_membership_projection(
    session: AsyncSession,
    *,
    user: User,
    preferred_unit: OrganisationUnit | None,
    affected_unit_ids: set[UUID],
    at: datetime | None = None,
) -> None:
    """Rebuild the compatibility projection from authoritative active histories."""

    now = datetime.now(UTC)
    effective_at = at or now
    current_unit_ids = set(
        await session.scalars(
            select(TeamMembership.team_id).where(
                TeamMembership.user_id == user.id,
                TeamMembership.effective_from <= effective_at,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > effective_at,
                ),
            )
        )
    )
    await session.execute(
        delete(UserOrganisationMembership).where(
            UserOrganisationMembership.user_id == user.id
        )
    )
    session.add_all(
        [
            UserOrganisationMembership(user_id=user.id, unit_id=unit_id)
            for unit_id in current_unit_ids
        ]
    )
    unit = preferred_unit
    if unit is None and current_unit_ids:
        unit = await session.scalar(
            select(OrganisationUnit)
            .where(OrganisationUnit.id.in_(current_unit_ids))
            .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            .limit(1)
        )
    user.scope = getattr(unit, "name", "Unassigned workspace Member")
    user.version += 1
    user.credential_version += 1
    await session.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.flush()
    delivery_ids = set(
        await session.scalars(
            select(OrganisationUnit.id).where(
                OrganisationUnit.id.in_(affected_unit_ids),
                OrganisationUnit.kind == OrganisationKind.TEAM,
            )
        )
    )
    if delivery_ids:
        await SqlAlchemyAdminRepository(session).recalculate_teams(delivery_ids)
