"""Activation of scheduled team-membership projection changes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import User, UserRole
from istari_service.organisation_models import (
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from istari_service.team_models import (
    TeamActivityType,
    TeamMembership,
)


async def synchronise_due_team_memberships(
    session: AsyncSession, at: datetime | None = None
) -> int:
    """Apply scheduled timeline changes to the compatibility projection."""

    effective_at = at or datetime.now(UTC)
    users = list(
        await session.scalars(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                User.role.in_(
                    [UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST]
                ),
                TeamMembership.effective_from <= effective_at,
            )
            .distinct()
        )
    )
    if not users:
        return 0
    user_ids = {user.id for user in users}
    effective_memberships = list(
        await session.scalars(
            select(TeamMembership).where(
                TeamMembership.user_id.in_(user_ids),
                TeamMembership.effective_from <= effective_at,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > effective_at,
                ),
            )
        )
    )
    effective_by_user = {
        membership.user_id: membership for membership in effective_memberships
    }
    projected_rows = (
        await session.execute(
            select(
                UserOrganisationMembership.user_id,
                UserOrganisationMembership.unit_id,
            ).where(UserOrganisationMembership.user_id.in_(user_ids))
        )
    ).all()
    projected_by_user: dict[UUID, set[UUID]] = {}
    for user_id, unit_id in projected_rows:
        projected_by_user.setdefault(user_id, set()).add(unit_id)
    changed = 0
    repository = SqlAlchemyTeamMembershipRepository(session)
    for user in users:
        current = effective_by_user.get(user.id)
        team_id = current.team_id if current else None
        projected_ids = projected_by_user.get(user.id, set())
        next_ids = {team_id} if team_id else set()
        if projected_ids == next_ids:
            continue
        team = await session.get(OrganisationUnit, team_id) if team_id else None
        await repository._set_projection(user, team, projected_ids | next_ids)
        if current is not None:
            repository._activity(
                current,
                None,
                TeamActivityType.TRANSFER_ACTIVATED,
                "A scheduled Analyst transfer became effective.",
            )
        changed += 1
    return changed
