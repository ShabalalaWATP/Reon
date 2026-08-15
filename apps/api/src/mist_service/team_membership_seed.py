"""Idempotent effective membership history for the synthetic baseline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.team_models import TeamMembership, WorkspacePosition


async def seed_team_membership_history(
    session: AsyncSession,
    desired_projection: set[tuple[UUID, UUID, WorkspacePosition]],
    unit_ids: set[UUID],
) -> None:
    desired = {
        (user_id, unit_id, position)
        for user_id, unit_id, position in desired_projection
        if unit_id in unit_ids
    }
    if not desired:
        return
    user_ids = {user_id for user_id, _, _ in desired}
    existing = {
        (membership.user_id, membership.team_id)
        for membership in await session.scalars(
            select(TeamMembership).where(TeamMembership.user_id.in_(user_ids))
        )
    }
    now = datetime.now(UTC)
    session.add_all(
        TeamMembership(
            user_id=user_id,
            team_id=team_id,
            workspace_position=position,
            effective_from=now,
            start_projected_at=now,
            start_reason="Established synthetic team baseline.",
        )
        for user_id, team_id, position in desired
        if (user_id, team_id) not in existing
    )
