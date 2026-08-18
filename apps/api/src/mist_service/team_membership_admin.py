"""History alignment for Platform Administrator membership changes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.errors import InvalidAdministrationChange
from mist_service.models import User
from mist_service.repositories.team_memberships import (
    SqlAlchemyTeamMembershipRepository,
)
from mist_service.roster_disposition import reject_active_roster_assignments
from mist_service.team_models import (
    TeamActivityType,
    TeamMembership,
    WorkspacePosition,
)


async def align_admin_workspace_memberships(
    session: AsyncSession,
    *,
    user: User,
    next_unit_ids: set[UUID],
    workspace_position: WorkspacePosition | None,
    actor_id: UUID,
    at: datetime | None = None,
) -> None:
    """Align authoritative effective histories with an Administrator change."""

    effective_at = at or datetime.now(UTC)
    memberships = list(
        await session.scalars(
            select(TeamMembership)
            .where(
                TeamMembership.user_id == user.id,
                TeamMembership.effective_until.is_(None),
            )
            .order_by(TeamMembership.effective_from, TeamMembership.id)
            .with_for_update()
        )
    )
    _require(
        not any(_as_utc(item.effective_from) > effective_at for item in memberships),
        InvalidAdministrationChange(
            "Resolve this account's scheduled workspace transfer first."
        ),
    )
    position = workspace_position or WorkspacePosition.MEMBER
    retained: set[UUID] = set()
    reason = "Platform Administrator updated the account workspace membership."
    repository = SqlAlchemyTeamMembershipRepository(session)
    if any(
        item.team_id not in next_unit_ids or item.workspace_position is not position
        for item in memberships
    ):
        await reject_active_roster_assignments(session, user.id, effective_at)
    for membership in memberships:
        keep = (
            membership.team_id in next_unit_ids
            and membership.workspace_position is position
        )
        if keep:
            retained.add(membership.team_id)
            continue
        membership.effective_until = effective_at
        membership.ended_by_user_id = actor_id
        membership.end_reason = reason
        membership.end_projected_at = effective_at
        membership.version += 1
        repository._activity(
            membership,
            actor_id,
            TeamActivityType.MEMBERSHIP_ENDED,
            "An account membership was ended by a Platform Administrator.",
        )
    for unit_id in sorted(next_unit_ids - retained, key=str):
        membership = TeamMembership(
            user_id=user.id,
            team_id=unit_id,
            workspace_position=position,
            effective_from=effective_at,
            started_by_user_id=actor_id,
            start_reason=reason,
            start_projected_at=effective_at,
        )
        session.add(membership)
        await session.flush()
        repository._activity(
            membership,
            actor_id,
            TeamActivityType.MEMBER_ADDED,
            "An account joined the workspace through Platform Administration.",
        )


def _require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
