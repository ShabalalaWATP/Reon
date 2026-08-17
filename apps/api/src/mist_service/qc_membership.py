"""Exact live membership rules for the combined QC workspace.

Two QC positions exist, mirroring delivery teams. A QC User (member position)
performs quality review. A QC Manager (manager position) performs quality
review and holds release accountability. Review visibility therefore accepts
any live position, while release remains manager-only, so the two predicates
below must never be collapsed into one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import User, UserRole
from mist_service.organisation_seed import organisation_id
from mist_service.team_models import TeamMembership, WorkspacePosition

QC_TEAM_CODE = "QC_TEAM"
QC_TEAM_ID = organisation_id(QC_TEAM_CODE)


def _live_qc_position_condition(
    user_id: Any,
    at: Any,
    position: WorkspacePosition | None,
) -> ColumnElement[bool]:
    conditions = [
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == QC_TEAM_ID,
        TeamMembership.effective_from <= at,
        or_(
            TeamMembership.effective_until.is_(None),
            TeamMembership.effective_until > at,
        ),
    ]
    if position is not None:
        conditions.append(TeamMembership.workspace_position == position)
    return exists().where(*conditions)


def live_qc_membership_condition(
    user_id: Any,
    at: Any,
) -> ColumnElement[bool]:
    """Return a predicate for any exact, current QC membership.

    This grants quality-review visibility to QC Users and QC Managers alike.
    It must not be used to authorise release; see the manager predicate.
    """

    return _live_qc_position_condition(user_id, at, None)


def live_qc_manager_condition(
    user_id: Any,
    at: Any,
) -> ColumnElement[bool]:
    """Return a predicate for an exact, current QC Manager membership only."""

    return _live_qc_position_condition(user_id, at, WorkspacePosition.MANAGER)


async def is_live_qc_manager(
    session: AsyncSession, user_id: UUID, *, at: datetime
) -> bool:
    """Recheck account state, role and manager membership in one query.

    Release accountability rests on this check alone, so it deliberately
    requires the manager position rather than any QC membership.
    """

    match = await session.scalar(
        select(User.id).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.role == UserRole.QUALITY_RELEASE,
            live_qc_manager_condition(User.id, at),
        )
    )
    return match is not None


async def is_live_qc_member(
    session: AsyncSession, user_id: UUID, *, at: datetime
) -> bool:
    """Recheck active account, role and any current QC workspace position."""

    match = await session.scalar(
        select(User.id).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.role == UserRole.QUALITY_RELEASE,
            live_qc_membership_condition(User.id, at),
        )
    )
    return match is not None
