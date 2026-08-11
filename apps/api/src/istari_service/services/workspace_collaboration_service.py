"""Authorisation for bounded workspace collaboration."""

from __future__ import annotations

import builtins
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import TeamWorkspaceNotFound
from istari_service.management_models import ManagementAction
from istari_service.repositories.management import resolve_management_scope
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.repositories.workspace_collaboration import (
    WorkspaceCollaborationRepository,
)
from istari_service.schemas.workspace_collaboration import (
    WorkspaceRecordCreate,
    WorkspaceRecordResolve,
    WorkspaceRecordView,
)


class WorkspaceCollaborationService:
    def __init__(
        self,
        views: SqlAlchemyTeamWorkspaceRepository,
        records: WorkspaceCollaborationRepository,
    ) -> None:
        self._views = views
        self._records = records

    async def list(
        self, actor: Actor, unit_id: UUID
    ) -> builtins.list[WorkspaceRecordView]:
        await self._views.require_read(actor.id, unit_id)
        return await self._records.list(unit_id)

    async def create(
        self, actor: Actor, unit_id: UUID, command: WorkspaceRecordCreate
    ) -> builtins.list[WorkspaceRecordView]:
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
        await self._authorise(actor, unit_id, command.grant_id)
        await self._records.resolve(unit_id, record_id, actor.id, command)
        return await self._records.list(unit_id)

    async def _authorise(self, actor: Actor, unit_id: UUID, grant_id: UUID) -> None:
        access = await self._views.require_read(actor.id, unit_id)
        if ManagementAction.ROSTER not in access.permissions:
            raise TeamWorkspaceNotFound()
        scope = await resolve_management_scope(
            self._records.session,
            subject_user_id=actor.id,
            grant_id=grant_id,
            target_unit_id=unit_id,
            action=ManagementAction.ROSTER,
            lock=True,
        )
        if scope is None or scope.root_unit_id != unit_id:
            raise TeamWorkspaceNotFound()
