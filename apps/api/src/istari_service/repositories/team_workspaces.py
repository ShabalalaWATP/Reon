"""Read models and final-boundary access for team workspaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial, reduce
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.board_models import WorkPackage, WorkPackageStatus
from istari_service.errors import TeamWorkspaceNotFound
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from istari_service.models import RequestStatus, ServiceRequest, User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    TeamActivity,
    TeamMember,
    TeamWorkspaceAccess,
    TeamWorkspaceOverview,
)
from istari_service.team_models import TeamActivityEvent, TeamMembership
from istari_service.team_workspace_views import (
    access_pair,
    activity_view,
    current_membership_pair,
    eligible_view,
    member_user_id,
    member_view,
    role_count_pair,
    user_id,
    work_count_pair,
)

TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}
WORKSPACE_ACTIONS = {
    ManagementAction.ROSTER,
    ManagementAction.CALENDAR,
    ManagementAction.BOARD,
    ManagementAction.CAPACITY,
    ManagementAction.STATISTICS,
}


@dataclass(slots=True)
class _Authority:
    team: OrganisationUnit
    grant_id: UUID | None = None
    permissions: set[ManagementAction] = field(default_factory=set)


class SqlAlchemyTeamWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_access(
        self, actor_id: UUID, at: datetime | None = None
    ) -> list[TeamWorkspaceAccess]:
        effective_at = at or datetime.now(UTC)
        own_teams = list(
            await self.session.scalars(
                select(OrganisationUnit)
                .join(
                    UserOrganisationMembership,
                    UserOrganisationMembership.unit_id == OrganisationUnit.id,
                )
                .where(
                    UserOrganisationMembership.user_id == actor_id,
                    OrganisationUnit.kind == OrganisationKind.TEAM,
                    OrganisationUnit.is_configured.is_(True),
                )
            )
        )
        authority = dict(map(_own_authority, own_teams))
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
                    OrganisationUnit.kind == OrganisationKind.TEAM,
                    OrganisationUnit.is_configured.is_(True),
                    User.is_active.is_(True),
                )
                .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            )
        ).all()
        reduce(_merge_authority, rows, authority)
        return list(map(self._access, authority.values()))

    async def require_read(self, actor_id: UUID, team_id: UUID) -> TeamWorkspaceAccess:
        access_by_team = dict(map(access_pair, await self.list_access(actor_id)))
        try:
            return access_by_team[team_id]
        except KeyError as error:
            raise TeamWorkspaceNotFound() from error

    async def overview(self, actor_id: UUID, team_id: UUID) -> TeamWorkspaceOverview:
        access = await self.require_read(actor_id, team_id)
        now = datetime.now(UTC)
        member_rows = (
            await self.session.execute(
                select(User.role, func.count(TeamMembership.id))
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
                .group_by(User.role)
            )
        ).all()
        counts = dict(map(role_count_pair, member_rows))
        today = datetime.now(UTC).date()
        active_condition = RequestAnalyticsFact.current_status.not_in(TERMINAL_STATUSES)
        active, due_soon, overdue = (
            await self.session.execute(
                select(
                    func.count(RequestAnalyticsFact.request_id).filter(
                        active_condition
                    ),
                    func.count(RequestAnalyticsFact.request_id).filter(
                        active_condition,
                        RequestAnalyticsFact.required_by >= today,
                        RequestAnalyticsFact.required_by <= today + timedelta(days=7),
                    ),
                    func.count(RequestAnalyticsFact.request_id).filter(
                        active_condition,
                        RequestAnalyticsFact.required_by < today,
                    ),
                ).where(RequestAnalyticsFact.team_unit_id == team_id)
            )
        ).one()
        return TeamWorkspaceOverview(
            access=access,
            manager_count=counts.get(UserRole.DELIVERY_TEAM_LEAD, 0),
            analyst_count=counts.get(UserRole.DELIVERY_SPECIALIST, 0),
            active_work_count=active or 0,
            due_soon_count=due_soon or 0,
            overdue_count=overdue or 0,
        )

    async def people(
        self, actor_id: UUID, team_id: UUID, *, reveal_reasons: bool
    ) -> list[TeamMember]:
        await self.require_read(actor_id, team_id)
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
        active_counts = await self._active_work_counts(set(map(member_user_id, rows)))
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
        await self.require_read(actor_id, team_id)
        now = datetime.now(UTC)
        analysts = list(
            await self.session.scalars(
                select(User)
                .where(
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    User.is_active.is_(True),
                )
                .order_by(User.display_name, User.id)
                .limit(500)
            )
        )
        analyst_ids = set(map(user_id, analysts))
        active_counts = await self._active_work_counts(analyst_ids)
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
        await self.require_read(actor_id, team_id)
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

    async def _active_work_counts(self, user_ids: set[UUID]) -> dict[UUID, int]:
        request_counts = (
            select(
                ServiceRequest.assigned_specialist_id.label("user_id"),
                func.count(ServiceRequest.id).label("active_count"),
            )
            .where(
                ServiceRequest.assigned_specialist_id.in_(user_ids),
                ServiceRequest.status.not_in(TERMINAL_STATUSES),
            )
            .group_by(ServiceRequest.assigned_specialist_id)
        )
        package_counts = (
            select(
                WorkPackage.owner_user_id.label("user_id"),
                func.count(WorkPackage.id).label("active_count"),
            )
            .where(
                WorkPackage.owner_user_id.in_(user_ids),
                WorkPackage.status.not_in(
                    {WorkPackageStatus.DONE, WorkPackageStatus.CANCELLED}
                ),
            )
            .group_by(WorkPackage.owner_user_id)
        )
        combined = request_counts.union_all(package_counts).subquery()
        rows = (
            await self.session.execute(
                select(combined.c.user_id, func.sum(combined.c.active_count)).group_by(
                    combined.c.user_id
                )
            )
        ).all()
        return dict(map(work_count_pair, rows))

    @staticmethod
    def _access(authority: _Authority) -> TeamWorkspaceAccess:
        return TeamWorkspaceAccess(
            team_id=authority.team.id,
            team_code=authority.team.code,
            team_name=authority.team.name,
            grant_id=authority.grant_id,
            permissions=sorted(authority.permissions, key=lambda action: action.value),
        )


def _merge_authority(
    authority: dict[UUID, _Authority],
    row: Any,
) -> dict[UUID, _Authority]:
    grant, action, team = row
    item = authority.setdefault(team.id, _Authority(team=team))
    item.grant_id = grant.id
    item.permissions.add(action)
    return authority


def _own_authority(team: OrganisationUnit) -> tuple[UUID, _Authority]:
    return team.id, _Authority(team=team)
