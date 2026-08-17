from __future__ import annotations

from datetime import UTC, datetime
from functools import partial, reduce
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mist_service.errors import TeamWorkspaceNotFound
from mist_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from mist_service.models import User, UserRole
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
)
from mist_service.repositories.team_memberships import MEMBER_ROLE_BY_KIND
from mist_service.repositories.team_workspace_authority import (
    WorkspaceAuthority as _Authority,
)
from mist_service.repositories.team_workspace_authority import (
    merge_authority as _merge_authority,
)
from mist_service.repositories.team_workspace_authority import (
    own_authority as _own_authority,
)
from mist_service.repositories.team_workspace_authority import workspace_views
from mist_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    TeamActivity,
    TeamMember,
    TeamWorkspaceAccess,
    TeamWorkspaceOverview,
)
from mist_service.team_models import (
    TeamActivityEvent,
    TeamMembership,
    WorkspacePosition,
)
from mist_service.team_workspace_views import (
    activity_view,
    current_membership_pair,
    eligible_view,
    member_user_id,
    member_view,
    user_id,
)
from mist_service.workspace_workloads import active_work_counts, overview_work_counts

WORKSPACE_ACTIONS = {
    ManagementAction.ROSTER,
    ManagementAction.CALENDAR,
    ManagementAction.BOARD,
    ManagementAction.CAPACITY,
    ManagementAction.STATISTICS,
}


class SqlAlchemyTeamWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_access(
        self, actor_id: UUID, at: datetime | None = None
    ) -> list[TeamWorkspaceAccess]:
        authority = await self._authority(actor_id, at)
        return list(map(self._access, authority.values()))

    async def _authority(
        self, actor_id: UUID, at: datetime | None = None
    ) -> dict[UUID, _Authority]:
        effective_at = at or datetime.now(UTC)
        own_rows = (
            await self.session.execute(
                select(OrganisationUnit, TeamMembership.workspace_position)
                .join(
                    TeamMembership,
                    TeamMembership.team_id == OrganisationUnit.id,
                )
                .where(
                    TeamMembership.user_id == actor_id,
                    TeamMembership.effective_from <= effective_at,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > effective_at,
                    ),
                    OrganisationUnit.is_configured.is_(True),
                )
            )
        ).all()
        authority = dict(map(_own_authority, own_rows))
        rows = (
            await self.session.execute(
                select(ManagementGrant, ManagementGrantAction.action, OrganisationUnit)
                .join(
                    ManagementGrantAction,
                    ManagementGrantAction.grant_id == ManagementGrant.id,
                )
                .join(
                    OrganisationUnit,
                    OrganisationUnit.id == ManagementGrant.root_unit_id,
                )
                .join(User, User.id == ManagementGrant.subject_user_id)
                .where(
                    ManagementGrant.subject_user_id == actor_id,
                    ManagementGrant.effective_from <= effective_at,
                    or_(
                        ManagementGrant.effective_until.is_(None),
                        ManagementGrant.effective_until > effective_at,
                    ),
                    ManagementGrant.revoked_at.is_(None),
                    ManagementGrantAction.action.in_(WORKSPACE_ACTIONS),
                    OrganisationUnit.is_configured.is_(True),
                    User.is_active.is_(True),
                )
                .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            )
        ).all()
        reduce(_merge_authority, rows, authority)
        return authority

    async def require_read(self, actor_id: UUID, team_id: UUID) -> TeamWorkspaceAccess:
        authority = await self._authority(actor_id)
        try:
            return self._access(authority[team_id])
        except KeyError as error:
            raise TeamWorkspaceNotFound() from error

    async def require_projection_read(
        self,
        actor_id: UUID,
        team_id: UUID,
        required_action: ManagementAction,
    ) -> TeamWorkspaceAccess:
        authority = await self._authority(actor_id)
        item = authority.get(team_id)
        if item is None or (
            item.position is None and required_action not in item.permissions
        ):
            raise TeamWorkspaceNotFound()
        return self._access(item)

    async def overview(self, actor_id: UUID, team_id: UUID) -> TeamWorkspaceOverview:
        authority = (await self._authority(actor_id)).get(team_id)
        if authority is None:
            raise TeamWorkspaceNotFound()
        access = self._access(authority)
        now = datetime.now(UTC)
        member_rows = (
            await self.session.execute(
                select(
                    TeamMembership.workspace_position,
                    User.role,
                    func.count(TeamMembership.id),
                )
                .join(User, User.id == TeamMembership.user_id)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                    User.is_active.is_(True),
                )
                .group_by(TeamMembership.workspace_position, User.role)
            )
        ).all()
        role_counts: dict[UserRole, int] = {}
        position_counts: dict[WorkspacePosition, int] = {}
        for position, role, count in member_rows:
            role_counts[role] = role_counts.get(role, 0) + count
            position_counts[position] = position_counts.get(position, 0) + count
        workload_visible = (
            authority.position is not None
            or bool(
                authority.permissions.intersection(
                    {ManagementAction.BOARD, ManagementAction.STATISTICS}
                )
            )
            if access.unit_kind is OrganisationKind.TEAM
            else ManagementAction.STATISTICS in authority.descendant_permissions
        )
        active, due_soon, overdue = (
            await overview_work_counts(self.session, team_id, access.unit_kind)
            if workload_visible
            else (0, 0, 0)
        )
        return TeamWorkspaceOverview(
            access=access,
            manager_count=position_counts.get(WorkspacePosition.MANAGER, 0),
            member_count=position_counts.get(WorkspacePosition.MEMBER, 0),
            analyst_count=role_counts.get(UserRole.DELIVERY_SPECIALIST, 0),
            active_work_count=active or 0,
            due_soon_count=due_soon or 0,
            overdue_count=overdue or 0,
            workload_visible=workload_visible,
        )

    async def people(
        self, actor_id: UUID, team_id: UUID, *, reveal_reasons: bool
    ) -> list[TeamMember]:
        await self.require_projection_read(actor_id, team_id, ManagementAction.ROSTER)
        now = datetime.now(UTC)
        rows = (
            await self.session.execute(
                select(TeamMembership, User)
                .join(User, User.id == TeamMembership.user_id)
                .where(TeamMembership.team_id == team_id)
                .order_by(TeamMembership.effective_from.desc(), User.display_name)
                .limit(500)
            )
        ).all()
        active_counts = await active_work_counts(
            self.session, set(map(member_user_id, rows))
        )
        return list(
            map(
                partial(
                    member_view,
                    now=now,
                    active_counts=active_counts,
                    reveal_reasons=reveal_reasons,
                ),
                rows,
            )
        )

    async def eligible_analysts(
        self, actor_id: UUID, team_id: UUID
    ) -> list[EligibleRosterAnalyst]:
        await self.require_projection_read(actor_id, team_id, ManagementAction.ROSTER)
        unit = await self.session.scalar(
            select(OrganisationUnit).where(OrganisationUnit.id == team_id)
        )
        if unit is None:
            raise TeamWorkspaceNotFound()
        now = datetime.now(UTC)
        analysts = list(
            await self.session.scalars(
                select(User)
                .where(
                    User.role == MEMBER_ROLE_BY_KIND[unit.kind],
                    User.is_active.is_(True),
                )
                .order_by(User.display_name, User.id)
                .limit(500)
            )
        )
        analyst_ids = set(map(user_id, analysts))
        active_counts = await active_work_counts(self.session, analyst_ids)
        membership_rows = (
            await self.session.execute(
                select(TeamMembership, OrganisationUnit)
                .join(OrganisationUnit, OrganisationUnit.id == TeamMembership.team_id)
                .where(
                    TeamMembership.user_id.in_(analyst_ids),
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                )
            )
        ).all()
        current_by_user = dict(map(current_membership_pair, membership_rows))
        return list(
            map(
                partial(
                    eligible_view,
                    current_by_user=current_by_user,
                    active_counts=active_counts,
                ),
                analysts,
            )
        )

    async def activity(self, actor_id: UUID, team_id: UUID) -> list[TeamActivity]:
        await self.require_projection_read(actor_id, team_id, ManagementAction.ROSTER)
        actor = aliased(User)
        subject = aliased(User)
        rows = (
            await self.session.execute(
                select(TeamActivityEvent, actor.display_name, subject.display_name)
                .outerjoin(actor, actor.id == TeamActivityEvent.actor_user_id)
                .join(subject, subject.id == TeamActivityEvent.subject_user_id)
                .where(TeamActivityEvent.team_id == team_id)
                .order_by(TeamActivityEvent.created_at.desc(), TeamActivityEvent.id)
                .limit(200)
            )
        ).all()
        return list(map(activity_view, rows))

    @staticmethod
    def _access(authority: _Authority) -> TeamWorkspaceAccess:
        return TeamWorkspaceAccess(
            team_id=authority.team.id,
            team_code=authority.team.code,
            team_name=authority.team.name,
            unit_kind=authority.team.kind,
            workspace_position=authority.position,
            grant_id=authority.grant_id,
            permissions=sorted(authority.permissions, key=lambda action: action.value),
            views=workspace_views(authority),
        )
