"""Transactional effective-dated roster persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import InvalidRosterChange, ObjectNotFound, StaleVersion
from istari_service.models import (
    User,
    UserRole,
)
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
)
from istari_service.roster_disposition import reject_active_roster_assignments
from istari_service.team_membership_projection import refresh_membership_projection
from istari_service.team_models import (
    TeamActivityEvent,
    TeamActivityType,
    TeamMembership,
    WorkspacePosition,
)

MEMBER_ROLE_BY_KIND = {
    OrganisationKind.ROOT: UserRole.INTAKE_TRIAGE,
    OrganisationKind.COMMAND: UserRole.SERVICE_COORDINATION,
    OrganisationKind.OPS_GROUP: UserRole.OPERATIONS_ALLOCATION,
    OrganisationKind.TEAM: UserRole.DELIVERY_SPECIALIST,
}


class SqlAlchemyTeamMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        actor_id: UUID,
        analyst_id: UUID,
        team_id: UUID,
        reason: str,
        at: datetime | None = None,
    ) -> TeamMembership:
        effective_at = _effective_at(at)
        team = await self._unit(team_id)
        analyst = await self._locked_member(analyst_id, team.kind)
        _require(
            not await self._has_membership_after(analyst.id, effective_at),
            InvalidRosterChange(
                "This Analyst already has a current or scheduled home team."
            ),
        )
        membership = TeamMembership(
            user_id=analyst.id,
            team_id=team.id,
            workspace_position=WorkspacePosition.MEMBER,
            effective_from=effective_at,
            started_by_user_id=actor_id,
            start_reason=reason.strip(),
        )
        self.session.add(membership)
        await self.session.flush()
        await self._set_projection(analyst, team, {team.id})
        membership.start_projected_at = effective_at
        self._activity(
            membership,
            actor_id,
            TeamActivityType.MEMBER_ADDED,
            "A Member joined the workspace.",
        )
        return membership

    async def end(
        self,
        *,
        actor_id: UUID,
        membership_id: UUID,
        team_id: UUID,
        expected_version: int,
        reason: str,
        at: datetime | None = None,
    ) -> TeamMembership:
        effective_at = _effective_at(at)
        membership = await self._locked_membership(membership_id, team_id)
        _require(membership.version == expected_version, StaleVersion())
        _require(
            self._is_effective(membership, effective_at),
            InvalidRosterChange("Only a current membership can be ended."),
        )
        await reject_active_roster_assignments(
            self.session, membership.user_id, effective_at
        )
        unit = await self._unit(team_id)
        analyst = await self._locked_member(membership.user_id, unit.kind)
        membership.effective_until = effective_at
        membership.ended_by_user_id = actor_id
        membership.end_reason = reason.strip()
        membership.version += 1
        await self.session.flush()
        await self._set_projection(analyst, None, {team_id})
        membership.end_projected_at = effective_at
        self._activity(
            membership,
            actor_id,
            TeamActivityType.MEMBERSHIP_ENDED,
            "A Member left the workspace.",
        )
        return membership

    async def transfer(
        self,
        *,
        actor_id: UUID,
        analyst_id: UUID,
        target_team_id: UUID,
        current_membership_id: UUID,
        expected_version: int,
        effective_from: datetime,
        reason: str,
    ) -> TeamMembership:
        now = datetime.now(UTC)
        target_team = await self._unit(target_team_id)
        analyst = await self._locked_member(analyst_id, target_team.kind)
        current = await self._locked_membership_for_user(
            current_membership_id, analyst.id
        )
        _require(current.version == expected_version, StaleVersion())
        _require(
            self._is_effective(current, now),
            InvalidRosterChange("Select the Member's current membership."),
        )
        _require(
            current.team_id != target_team.id,
            InvalidRosterChange("The Member already belongs to this workspace."),
        )
        _require(
            effective_from >= now - timedelta(minutes=1),
            InvalidRosterChange("A transfer cannot begin in the past."),
        )
        effective_start = max(effective_from, now)
        _require(
            not await self._has_scheduled_membership(analyst.id, now),
            InvalidRosterChange("This Member already has a scheduled move."),
        )
        await reject_active_roster_assignments(
            self.session, analyst.id, effective_start
        )
        current.effective_until = effective_start
        current.ended_by_user_id = actor_id
        current.end_reason = reason.strip()
        current.version += 1
        next_membership = TeamMembership(
            user_id=analyst.id,
            team_id=target_team.id,
            workspace_position=WorkspacePosition.MEMBER,
            effective_from=effective_start,
            started_by_user_id=actor_id,
            start_reason=reason.strip(),
        )
        self.session.add(next_membership)
        await self.session.flush()
        if effective_start <= now:
            await self._set_projection(
                analyst, target_team, {current.team_id, target_team.id}
            )
            current.end_projected_at = now
            next_membership.start_projected_at = now
        self._activity(
            current,
            actor_id,
            TeamActivityType.TRANSFER_SCHEDULED,
            "A Member transfer was scheduled from this workspace.",
            {"effectiveFrom": effective_start.isoformat()},
        )
        self._activity(
            next_membership,
            actor_id,
            TeamActivityType.TRANSFER_SCHEDULED,
            "A Member transfer was scheduled into this workspace.",
            {"effectiveFrom": effective_start.isoformat()},
        )
        return next_membership

    async def _locked_member(self, user_id: UUID, unit_kind: OrganisationKind) -> User:
        analyst = await self.session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        _require(analyst is not None, ObjectNotFound())
        found = cast(User, analyst)
        _require(
            found.is_active and found.role is MEMBER_ROLE_BY_KIND[unit_kind],
            InvalidRosterChange("Select an active compatible workspace Member."),
        )
        return found

    async def _unit(self, team_id: UUID) -> OrganisationUnit:
        team = await self.session.scalar(
            select(OrganisationUnit).where(
                OrganisationUnit.id == team_id,
                OrganisationUnit.is_configured.is_(True),
            )
        )
        _require(team is not None, ObjectNotFound())
        return cast(OrganisationUnit, team)

    async def _locked_membership(
        self, membership_id: UUID, team_id: UUID
    ) -> TeamMembership:
        membership = await self.session.scalar(
            select(TeamMembership)
            .where(
                TeamMembership.id == membership_id,
                TeamMembership.team_id == team_id,
            )
            .with_for_update()
        )
        _require(membership is not None, ObjectNotFound())
        return cast(TeamMembership, membership)

    async def _locked_membership_for_user(
        self, membership_id: UUID, user_id: UUID
    ) -> TeamMembership:
        membership = await self.session.scalar(
            select(TeamMembership)
            .where(
                TeamMembership.id == membership_id,
                TeamMembership.user_id == user_id,
            )
            .with_for_update()
        )
        _require(membership is not None, ObjectNotFound())
        return cast(TeamMembership, membership)

    async def _has_membership_after(self, user_id: UUID, at: datetime) -> bool:
        return (
            await self.session.scalar(
                select(TeamMembership.id).where(
                    TeamMembership.user_id == user_id,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > at,
                    ),
                )
            )
            is not None
        )

    async def _has_scheduled_membership(self, user_id: UUID, at: datetime) -> bool:
        return (
            await self.session.scalar(
                select(TeamMembership.id).where(
                    TeamMembership.user_id == user_id,
                    TeamMembership.effective_from > at,
                )
            )
            is not None
        )

    async def _set_projection(
        self,
        analyst: User,
        team: OrganisationUnit | None,
        affected_team_ids: set[UUID],
        at: datetime | None = None,
    ) -> None:
        await refresh_membership_projection(
            self.session,
            user=analyst,
            preferred_unit=team,
            affected_unit_ids=affected_team_ids,
            at=at,
        )

    def _activity(
        self,
        membership: TeamMembership,
        actor_id: UUID | None,
        activity_type: TeamActivityType,
        summary: str,
        details: dict[str, str] | None = None,
    ) -> None:
        self.session.add(
            TeamActivityEvent(
                team_id=membership.team_id,
                actor_user_id=actor_id,
                subject_user_id=membership.user_id,
                membership_id=membership.id,
                type=activity_type,
                summary=summary,
                details=details or {},
            )
        )

    @staticmethod
    def _is_effective(membership: TeamMembership, at: datetime) -> bool:
        effective_from = _as_utc(membership.effective_from)
        effective_until = (
            _as_utc(membership.effective_until)
            if membership.effective_until is not None
            else None
        )
        return effective_from <= at and (
            effective_until is None or effective_until > at
        )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _effective_at(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
