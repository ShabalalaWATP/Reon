"""Team workspace queries and Manager-controlled roster use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from mist_service.domain import Actor
from mist_service.errors import InvalidRosterChange, TeamWorkspaceNotFound
from mist_service.identity_context import require_staff_context
from mist_service.management_models import ManagementAction
from mist_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    EndMembershipCommand,
    RosterCommand,
    TeamActivity,
    TeamMember,
    TeamMemberProfile,
    TeamWorkspaceAccess,
    TeamWorkspaceOverview,
    TransferCommand,
)
from mist_service.services.team_workspace_ports import (
    ExactManagementScopePort,
    TeamMemberProfileReadPort,
    TeamMembershipMutationPort,
    TeamWorkspaceViewPort,
)
from mist_service.team_models import WorkspacePosition


class TeamWorkspaceService:
    def __init__(
        self,
        views: TeamWorkspaceViewPort,
        memberships: TeamMembershipMutationPort,
        profiles: TeamMemberProfileReadPort,
        management_scopes: ExactManagementScopePort,
    ) -> None:
        self._views = views
        self._memberships = memberships
        self._profiles = profiles
        self._management_scopes = management_scopes

    async def list_access(self, actor: Actor) -> list[TeamWorkspaceAccess]:
        self._require_staff(actor)
        return await self._views.list_access(actor.id)

    async def overview(self, actor: Actor, team_id: UUID) -> TeamWorkspaceOverview:
        self._require_staff(actor)
        return await self._views.overview(actor.id, team_id)

    async def people(self, actor: Actor, team_id: UUID) -> list[TeamMember]:
        self._require_staff(actor)
        access = await self._views.require_projection_read(
            actor.id, team_id, ManagementAction.ROSTER
        )
        reveal_reasons = (
            access.workspace_position is WorkspacePosition.MANAGER
            and ManagementAction.ROSTER in access.permissions
        )
        return await self._views.people(
            actor.id, team_id, reveal_reasons=reveal_reasons
        )

    async def member_profile(
        self, actor: Actor, team_id: UUID, member_id: UUID
    ) -> TeamMemberProfile:
        self._require_staff(actor)
        return await self._profiles.get(actor.id, team_id, member_id)

    async def eligible_analysts(
        self, actor: Actor, team_id: UUID, grant_id: UUID
    ) -> list[EligibleRosterAnalyst]:
        self._require_staff(actor)
        await self._authorise_roster(actor, team_id, grant_id)
        return await self._views.eligible_analysts(actor.id, team_id)

    async def activity(self, actor: Actor, team_id: UUID) -> list[TeamActivity]:
        self._require_staff(actor)
        return await self._views.activity(actor.id, team_id)

    async def add(
        self, actor: Actor, team_id: UUID, command: RosterCommand
    ) -> list[TeamMember]:
        self._require_staff(actor)
        await self._authorise_roster(actor, team_id, command.grant_id, lock=True)
        await self._memberships.add(
            actor_id=actor.id,
            analyst_id=command.analyst_id,
            team_id=team_id,
            reason=command.reason,
        )
        return await self._views.people(actor.id, team_id, reveal_reasons=True)

    async def transfer(
        self, actor: Actor, team_id: UUID, command: TransferCommand
    ) -> list[TeamMember]:
        self._require_staff(actor)
        await self._authorise_roster(actor, team_id, command.grant_id, lock=True)
        now = datetime.now(UTC)
        _require(
            command.effective_from <= now + timedelta(days=366),
            InvalidRosterChange(
                "Schedule a transfer no more than 366 days in advance."
            ),
        )
        await self._memberships.transfer(
            actor_id=actor.id,
            analyst_id=command.analyst_id,
            target_team_id=team_id,
            current_membership_id=command.current_membership_id,
            expected_version=command.expected_version,
            effective_from=command.effective_from,
            reason=command.reason,
        )
        return await self._views.people(actor.id, team_id, reveal_reasons=True)

    async def end(
        self,
        actor: Actor,
        team_id: UUID,
        membership_id: UUID,
        command: EndMembershipCommand,
    ) -> list[TeamMember]:
        self._require_staff(actor)
        await self._authorise_roster(actor, team_id, command.grant_id, lock=True)
        await self._memberships.end(
            actor_id=actor.id,
            membership_id=membership_id,
            team_id=team_id,
            expected_version=command.expected_version,
            reason=command.reason,
        )
        return await self._views.people(actor.id, team_id, reveal_reasons=True)

    async def _authorise_roster(
        self,
        actor: Actor,
        team_id: UUID,
        grant_id: UUID,
        *,
        lock: bool = False,
    ) -> None:
        access = await self._views.require_read(actor.id, team_id)
        _require(
            access.workspace_position is WorkspacePosition.MANAGER,
            TeamWorkspaceNotFound(),
        )
        authorised = await self._management_scopes.authorises_exact_root(
            actor_id=actor.id,
            grant_id=grant_id,
            unit_id=team_id,
            action=ManagementAction.ROSTER,
            lock=lock,
        )
        _require(authorised, TeamWorkspaceNotFound())

    @staticmethod
    def _require_staff(actor: Actor) -> None:
        require_staff_context(actor, TeamWorkspaceNotFound())


def _require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
