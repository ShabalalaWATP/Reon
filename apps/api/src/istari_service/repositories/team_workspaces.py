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
from istari_service.errors import TeamWorkspaceNotFound
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
    OrganisationClosure,
)
from istari_service.models import RequestStatus, User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
)
from istari_service.repositories.team_memberships import MEMBER_ROLE_BY_KIND
from istari_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    TeamActivity,
    TeamMember,
    TeamWorkspaceAccess,
    TeamWorkspaceOverview,
)
from istari_service.team_models import (
    TeamActivityEvent,
    TeamMembership,
    WorkspacePosition,
)
from istari_service.team_workspace_views import (
    access_pair,
    activity_view,
    current_membership_pair,
    eligible_view,
    member_user_id,
    member_view,
    user_id,
)
from istari_service.workspace_workloads import active_work_counts

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
    position: WorkspacePosition | None = None
    grant_id: UUID | None = None
    permissions: set[ManagementAction] = field(default_factory=set)


class SqlAlchemyTeamWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_access(
        self, actor_id: UUID, at: datetime | None = None
    ) -> list[TeamWorkspaceAccess]:
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
        today = datetime.now(UTC).date()
        active_condition = RequestAnalyticsFact.current_status.not_in(TERMINAL_STATUSES)
        fact_scope = (
            RequestAnalyticsFact.team_unit_id == team_id
            if access.unit_kind is OrganisationKind.TEAM
            else RequestAnalyticsFact.team_unit_id.in_(
                select(OrganisationClosure.descendant_id).where(
                    OrganisationClosure.ancestor_id == team_id
                )
            )
        )
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
                ).where(fact_scope)
            )
        ).one()
        return TeamWorkspaceOverview(
            access=access,
            manager_count=position_counts.get(WorkspacePosition.MANAGER, 0),
            member_count=position_counts.get(WorkspacePosition.MEMBER, 0),
            analyst_count=role_counts.get(UserRole.DELIVERY_SPECIALIST, 0),
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
        await self.require_read(actor_id, team_id)
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
            views=_workspace_views(authority.team.kind),
        )


def _merge_authority(
    authority: dict[UUID, _Authority],
    row: Any,
) -> dict[UUID, _Authority]:
    grant, action, team = row
    item = authority.setdefault(team.id, _Authority(team=team))
    if item.grant_id is None or action in {
        ManagementAction.ROSTER,
        ManagementAction.CALENDAR,
    }:
        item.grant_id = grant.id
    item.permissions.add(action)
    return authority


def _own_authority(row: Any) -> tuple[UUID, _Authority]:
    unit, position = row
    return unit.id, _Authority(team=unit, position=position)


def _workspace_views(kind: OrganisationKind) -> list[str]:
    if kind is OrganisationKind.TEAM:
        return [
            "OVERVIEW",
            "BOARD",
            "CALENDAR",
            "PEOPLE",
            "PLANNING",
            "STATISTICS",
            "ACTIVITY",
        ]
    return [
        "OVERVIEW",
        "QUEUE",
        "CALENDAR",
        "PEOPLE",
        "STATISTICS",
        "HANDOVER",
        "ACTIVITY",
    ]
