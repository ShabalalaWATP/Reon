"""Idempotent effective membership history for the synthetic baseline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.team_models import TeamMembership


async def seed_team_membership_history(
    session: AsyncSession,
    desired_projection: set[tuple[UUID, UUID]],
    team_ids: set[UUID],
) -> None:
    desired = {
        (user_id, unit_id)
        for user_id, unit_id in desired_projection
        if unit_id in team_ids
    }
    if not desired:
        return
    user_ids = {user_id for user_id, _ in desired}
    historical_user_ids = set(
        await session.scalars(
            select(TeamMembership.user_id).where(TeamMembership.user_id.in_(user_ids))
        )
    )
    now = datetime.now(UTC)
    session.add_all(
        TeamMembership(
            user_id=user_id,
            team_id=team_id,
            effective_from=now,
            start_reason="Established synthetic team baseline.",
        )
        for user_id, team_id in desired
        if user_id not in historical_user_ids
    )
