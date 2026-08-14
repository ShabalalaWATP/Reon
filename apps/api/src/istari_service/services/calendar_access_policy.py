"""Application policy for calendar privacy and management authority."""

from __future__ import annotations

from uuid import UUID

from istari_service.calendar_models import CalendarEventKind
from istari_service.calendar_ports import (
    CalendarEventRecord,
    CalendarIdentityPort,
    CalendarManagementPort,
)
from istari_service.domain import Actor
from istari_service.errors import CalendarItemNotFound, TeamWorkspaceNotFound
from istari_service.management_models import ManagementAction
from istari_service.request_identity_policy import require_requester_excluded
from istari_service.services.calendar_validation import require
from istari_service.services.team_workspace_ports import TeamWorkspaceReadPort


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
