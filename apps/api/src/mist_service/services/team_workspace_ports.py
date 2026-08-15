"""Small application ports for authorised team-workspace use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.management_models import ManagementAction
from mist_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    TeamActivity,
    TeamMember,
    TeamMemberProfile,
    TeamWorkspaceAccess,
    TeamWorkspaceOverview,
)
from mist_service.schemas.workspace_collaboration import (
    WorkspaceRecordCreate,
    WorkspaceRecordResolve,
    WorkspaceRecordView,
)


class TeamWorkspaceReadPort(Protocol):
    """Authorise exact-team read access for dependent workspace features."""

    async def require_read(
        self, actor_id: UUID, team_id: UUID
    ) -> TeamWorkspaceAccess: ...


class TeamWorkspaceViewPort(TeamWorkspaceReadPort, Protocol):
    """Serve the complete team-workspace query surface."""

    async def list_access(self, actor_id: UUID) -> list[TeamWorkspaceAccess]: ...

    async def overview(
        self, actor_id: UUID, team_id: UUID
    ) -> TeamWorkspaceOverview: ...

    async def people(
        self, actor_id: UUID, team_id: UUID, *, reveal_reasons: bool
    ) -> list[TeamMember]: ...

    async def eligible_analysts(
        self, actor_id: UUID, team_id: UUID
    ) -> list[EligibleRosterAnalyst]: ...

    async def activity(self, actor_id: UUID, team_id: UUID) -> list[TeamActivity]: ...


class TeamMembershipMutationPort(Protocol):
    """Persist roster changes after the service authorises an exact team."""

    async def add(
        self,
        *,
        actor_id: UUID,
        analyst_id: UUID,
        team_id: UUID,
        reason: str,
    ) -> object: ...

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
    ) -> object: ...

    async def end(
        self,
        *,
        actor_id: UUID,
        membership_id: UUID,
        team_id: UUID,
        expected_version: int,
        reason: str,
    ) -> object: ...


class TeamMemberProfileReadPort(Protocol):
    async def get(
        self, actor_id: UUID, team_id: UUID, member_id: UUID
    ) -> TeamMemberProfile: ...


class ExactManagementScopePort(Protocol):
    """Check a named grant without exposing persistence sessions to use cases."""

    async def authorises_exact_root(
        self,
        *,
        actor_id: UUID,
        grant_id: UUID,
        unit_id: UUID,
        action: ManagementAction,
        lock: bool,
    ) -> bool: ...


class WorkspaceCollaborationPort(Protocol):
    async def list(self, unit_id: UUID) -> list[WorkspaceRecordView]: ...

    async def create(
        self,
        unit_id: UUID,
        actor_id: UUID,
        command: WorkspaceRecordCreate,
    ) -> object: ...

    async def resolve(
        self,
        unit_id: UUID,
        record_id: UUID,
        actor_id: UUID,
        command: WorkspaceRecordResolve,
    ) -> object: ...
