"""Authorisation for bounded workspace collaboration."""

from __future__ import annotations

import builtins
from uuid import UUID

from mist_service.domain import Actor
from mist_service.errors import TeamWorkspaceNotFound
from mist_service.identity_context import require_staff_context
from mist_service.management_models import ManagementAction
from mist_service.schemas.workspace_collaboration import (
    WorkspaceRecordCreate,
    WorkspaceRecordResolve,
    WorkspaceRecordView,
)
from mist_service.services.team_workspace_ports import (
    ExactManagementScopePort,
    TeamWorkspaceReadPort,
    WorkspaceCollaborationPort,
)


class WorkspaceCollaborationService:
    def __init__(
        self,
        views: TeamWorkspaceReadPort,
        records: WorkspaceCollaborationPort,
        management_scopes: ExactManagementScopePort,
    ) -> None:
        self._views = views
        self._records = records
        self._management_scopes = management_scopes

    async def list(
        self, actor: Actor, unit_id: UUID
    ) -> builtins.list[WorkspaceRecordView]:
        self._require_staff(actor)
        await self._views.require_read(actor.id, unit_id)
        return await self._records.list(unit_id)

    async def create(
        self, actor: Actor, unit_id: UUID, command: WorkspaceRecordCreate
    ) -> builtins.list[WorkspaceRecordView]:
        self._require_staff(actor)
        await self._authorise(actor, unit_id, command.grant_id)
        await self._records.create(unit_id, actor.id, command)
        return await self._records.list(unit_id)

    async def resolve(
        self,
        actor: Actor,
        unit_id: UUID,
        record_id: UUID,
        command: WorkspaceRecordResolve,
    ) -> builtins.list[WorkspaceRecordView]:
        self._require_staff(actor)
        await self._authorise(actor, unit_id, command.grant_id)
        await self._records.resolve(unit_id, record_id, actor.id, command)
        return await self._records.list(unit_id)

    async def _authorise(self, actor: Actor, unit_id: UUID, grant_id: UUID) -> None:
        access = await self._views.require_read(actor.id, unit_id)
        if ManagementAction.ROSTER not in access.permissions:
            raise TeamWorkspaceNotFound()
        authorised = await self._management_scopes.authorises_exact_root(
            actor_id=actor.id,
            grant_id=grant_id,
            unit_id=unit_id,
            action=ManagementAction.ROSTER,
            lock=True,
        )
        if not authorised:
            raise TeamWorkspaceNotFound()

    @staticmethod
    def _require_staff(actor: Actor) -> None:
        require_staff_context(actor, TeamWorkspaceNotFound())
