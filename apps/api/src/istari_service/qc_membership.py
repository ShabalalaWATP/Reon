"""Exact live membership rules for the combined QC workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import User, UserRole
from istari_service.organisation_seed import organisation_id
from istari_service.team_models import TeamMembership, WorkspacePosition

QC_TEAM_CODE = "QC_TEAM"
QC_TEAM_ID = organisation_id(QC_TEAM_CODE)


def live_qc_membership_condition(
    user_id: Any,
    at: Any,
) -> ColumnElement[bool]:
    """Return a database predicate for an exact, current QC Manager membership."""

    return exists().where(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == QC_TEAM_ID,
        TeamMembership.workspace_position == WorkspacePosition.MANAGER,
        TeamMembership.effective_from <= at,
        or_(
            TeamMembership.effective_until.is_(None),
            TeamMembership.effective_until > at,
        ),
    )


async def is_live_qc_manager(
    session: AsyncSession, user_id: UUID, *, at: datetime
) -> bool:
    """Recheck account state, role and effective membership in one query."""

    match = await session.scalar(
        select(User.id).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.role == UserRole.QUALITY_RELEASE,
            live_qc_membership_condition(User.id, at),
        )
    )
    return match is not None
