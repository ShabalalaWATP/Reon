"""Application policy for calendar privacy and management authority."""

from __future__ import annotations

from uuid import UUID

from mist_service.calendar_models import CalendarEventKind
from mist_service.calendar_ports import (
    CalendarEventRecord,
    CalendarIdentityPort,
    CalendarManagementPort,
)
from mist_service.domain import Actor
from mist_service.errors import CalendarItemNotFound, TeamWorkspaceNotFound
from mist_service.management_models import ManagementAction
from mist_service.request_identity_policy import require_requester_excluded
from mist_service.services.calendar_validation import require
from mist_service.services.team_workspace_ports import TeamWorkspaceReadPort


class CalendarAccessPolicy:
    def __init__(
        self,
        calendar: CalendarIdentityPort,
        workspaces: TeamWorkspaceReadPort,
        management: CalendarManagementPort,
    ) -> None:
        self._calendar = calendar
        self._workspaces = workspaces
        self._management = management

    async def authorise_event_change(
        self, actor: Actor, event: CalendarEventRecord
    ) -> None:
        if (
            event.kind is CalendarEventKind.PERSONAL
            and event.subject_user_id == actor.id
        ):
            return
        if event.team_id is None:
            raise CalendarItemNotFound()
        await self.require_no_requester_conflict(
            actor, event.request_id, event.subject_user_id
        )
        access = await self._workspaces.require_read(actor.id, event.team_id)
        if (
            access.grant_id is None
            or ManagementAction.CALENDAR not in access.permissions
        ):
            raise CalendarItemNotFound()
        await self.authorise(
            actor, event.team_id, access.grant_id, ManagementAction.CALENDAR
        )

    async def require_no_requester_conflict(
        self, actor: Actor, request_id: UUID | None, subject_id: UUID
    ) -> None:
        if request_id is None:
            return
        requester_id = await self._calendar.request_requester_id(request_id)
        require_requester_excluded(
            requester_id,
            {actor.id, subject_id},
            CalendarItemNotFound(),
        )

    async def authorise(
        self,
        actor: Actor,
        team_id: UUID,
        grant_id: UUID,
        action: ManagementAction,
    ) -> None:
        require(
            await self._management.has_authority(actor, team_id, grant_id, action),
            TeamWorkspaceNotFound(),
        )
