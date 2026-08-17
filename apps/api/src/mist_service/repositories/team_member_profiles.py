"""Bounded professional profiles for authorised team colleagues."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.errors import TeamWorkspaceNotFound
from mist_service.management_models import ManagementAction
from mist_service.models import User
from mist_service.organisation_models import OrganisationUnit
from mist_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from mist_service.schemas.team_workspaces import TeamMemberProfile
from mist_service.team_models import TeamMembership
from mist_service.team_workspace_views import membership_state


class SqlAlchemyTeamMemberProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._workspaces = SqlAlchemyTeamWorkspaceRepository(session)

    async def get(
        self, actor_id: UUID, team_id: UUID, member_id: UUID
    ) -> TeamMemberProfile:
        await self._workspaces.require_projection_read(
            actor_id, team_id, ManagementAction.ROSTER
        )
        row = (
            await self.session.execute(
                select(TeamMembership, User, OrganisationUnit)
                .join(User, User.id == TeamMembership.user_id)
                .join(OrganisationUnit, OrganisationUnit.id == TeamMembership.team_id)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.user_id == member_id,
                )
                .order_by(
                    TeamMembership.effective_until.is_(None).desc(),
                    TeamMembership.effective_from.desc(),
                )
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            raise TeamWorkspaceNotFound()
        membership, user, team = row
        return TeamMemberProfile(
            account_id=user.id,
            name=user.display_name,
            email=user.email,
            role=user.role,
            team_id=team.id,
            team_name=team.name,
            workspace_position=membership.workspace_position,
            membership_state=membership_state(membership, datetime.now(UTC)),
            rank_or_grade=user.rank_or_grade,
            skills=user.skills,
            account_active=user.is_active,
        )
