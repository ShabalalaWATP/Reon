"""Final-boundary authority for exact-team planning scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import TeamWorkspaceNotFound
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.management import resolve_management_scope


async def authorise_planning_read(
    session: AsyncSession,
    actor: Actor,
    team_id: UUID,
    action: ManagementAction,
) -> None:
    """Allow a team member or a current exact-team content grant."""

    configured_team = await session.scalar(
        select(OrganisationUnit.id).where(
            OrganisationUnit.id == team_id,
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if team_id in actor.organisation_unit_ids and configured_team is not None:
        return
    now = datetime.now(UTC)
    grant = await session.scalar(
        select(ManagementGrant.id)
        .join(User, User.id == ManagementGrant.subject_user_id)
        .join(
            ManagementGrantAction,
            ManagementGrantAction.grant_id == ManagementGrant.id,
        )
        .join(OrganisationUnit, OrganisationUnit.id == ManagementGrant.root_unit_id)
        .where(
            ManagementGrant.subject_user_id == actor.id,
            ManagementGrant.root_unit_id == team_id,
            ManagementGrantAction.action == action,
            ManagementGrant.effective_from <= now,
            or_(
                ManagementGrant.effective_until.is_(None),
                ManagementGrant.effective_until > now,
            ),
            ManagementGrant.revoked_at.is_(None),
            User.is_active.is_(True),
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if grant is None:
        raise TeamWorkspaceNotFound()


async def authorise_planning_preview(
    session: AsyncSession,
    actor: Actor,
    team_id: UUID,
    grant_id: UUID,
) -> None:
    """Require one current exact-team grant with board and capacity actions."""

    if actor.role is not UserRole.DELIVERY_TEAM_LEAD:
        raise TeamWorkspaceNotFound()
    for action in (ManagementAction.BOARD, ManagementAction.CAPACITY):
        scope = await resolve_management_scope(
            session,
            subject_user_id=actor.id,
            grant_id=grant_id,
            target_unit_id=team_id,
            action=action,
            lock=True,
        )
        if scope is None or scope.root_unit_id != team_id:
            raise TeamWorkspaceNotFound()
