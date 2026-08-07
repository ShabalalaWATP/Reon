"""History alignment for Platform Administrator membership changes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import InvalidAdministrationChange
from istari_service.models import User
from istari_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from istari_service.team_models import TeamActivityType, TeamMembership


async def align_admin_team_membership(
    session: AsyncSession,
    *,
    user: User,
    next_team_id: UUID | None,
    actor_id: UUID,
    at: datetime | None = None,
) -> None:
    """Preserve the timeline while the established admin projection is replaced."""

    effective_at = at or datetime.now(UTC)
    memberships = list(
        await session.scalars(
            select(TeamMembership)
            .where(
                TeamMembership.user_id == user.id,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > effective_at,
                ),
            )
            .order_by(TeamMembership.effective_from)
            .with_for_update()
        )
    )
    scheduled_id = await session.scalar(
        select(TeamMembership.id).where(
            TeamMembership.user_id == user.id,
            TeamMembership.effective_from > effective_at,
        )
    )
    _require(
        scheduled_id is None,
        InvalidAdministrationChange(
            "Resolve this account's scheduled team transfer first."
        ),
    )
    current = next(iter(memberships), None)
    reason = "Platform Administrator updated the account team membership."
    repository = SqlAlchemyTeamMembershipRepository(session)
    if current is not None:
        current.effective_until = effective_at
        current.ended_by_user_id = actor_id
        current.end_reason = reason
        current.version += 1
        repository._activity(
            current,
            actor_id,
            TeamActivityType.MEMBERSHIP_ENDED,
            "An account membership was ended by a Platform Administrator.",
        )
    if next_team_id is None:
        return
    next_membership = TeamMembership(
        user_id=user.id,
        team_id=next_team_id,
        effective_from=effective_at,
        started_by_user_id=actor_id,
        start_reason=reason,
    )
    session.add(next_membership)
    await session.flush()
    repository._activity(
        next_membership,
        actor_id,
        TeamActivityType.MEMBER_ADDED,
        "An account joined the team through Platform Administration.",
    )


def _require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
