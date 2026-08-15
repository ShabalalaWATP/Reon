"""Calendar use cases with final-boundary scope and lifecycle checks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from mist_service.calendar_models import (
    CalendarEventKind,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)
from mist_service.calendar_ports import (
    CalendarCapacityPort,
    CalendarManagementPort,
    CalendarRepositoryPort,
)
from mist_service.domain import Actor
from mist_service.errors import (
    CalendarItemNotFound,
    InvalidCalendarChange,
)
from mist_service.identity_context import require_staff_context
from mist_service.management_models import ManagementAction
from mist_service.organisation_models import OrganisationKind
from mist_service.schemas.calendar import (
    CalendarEventCommand,
    CalendarEventResult,
    CalendarEventUpdate,
    CalendarOccurrence,
    CapacityCommitCommand,
    CapacityPreview,
    CapacityPreviewCommand,
    CapacitySnapshot,
    CommitmentCommand,
    CommitmentDecisionCommand,
    FutureSplitCommand,
    OccurrenceCancelCommand,
    OccurrenceEditCommand,
    PersonalEventCommand,
    TeamEventCommand,
)
from mist_service.services.calendar_access_policy import CalendarAccessPolicy
from mist_service.services.calendar_validation import require as _require
from mist_service.services.calendar_validation import (
    require_occurrence as _require_occurrence,
)
from mist_service.services.calendar_validation import result as _result
from mist_service.services.calendar_validation import (
    validate_capacity_range as _capacity_range,
)
from mist_service.services.calendar_validation import validate_command as _command
from mist_service.services.calendar_validation import validate_range as _range
from mist_service.services.calendar_validation import validate_zone as _zone
from mist_service.services.team_workspace_ports import TeamWorkspaceReadPort

__all__ = [
    "CalendarService",
    "_capacity_range",
    "_command",
    "_range",
    "_require",
    "_zone",
]


class CalendarService:
    def __init__(
        self,
        calendar: CalendarRepositoryPort,
        workspaces: TeamWorkspaceReadPort,
        capacity: CalendarCapacityPort,
        management: CalendarManagementPort,
    ) -> None:
        self._calendar = calendar
        self._workspaces = workspaces
        self._capacity = capacity
        self._access = CalendarAccessPolicy(calendar, workspaces, management)

    async def personal(
        self, actor: Actor, start: datetime, end: datetime
    ) -> list[CalendarOccurrence]:
        self._require_staff(actor)
        _range(start, end)
        return await self._calendar.list_personal(actor.id, start, end)

    async def team(
        self, actor: Actor, team_id: UUID, start: datetime, end: datetime
    ) -> list[CalendarOccurrence]:
        self._require_staff(actor)
        _range(start, end)
        await self._workspaces.require_read(actor.id, team_id)
        return await self._calendar.list_team(team_id, start, end)

    async def create_personal(
        self, actor: Actor, command: PersonalEventCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        _command(command)
        _require(
            command.visibility
            in {CalendarVisibility.TEAM_DETAIL, CalendarVisibility.PRIVATE},
            InvalidCalendarChange(
                "Choose team-visible detail or select Private appointment."
            ),
        )
        event = await self._calendar.create_event(
            actor_id=actor.id,
            subject_id=actor.id,
            team_id=None,
            request_id=None,
            kind=CalendarEventKind.PERSONAL,
            commitment_status=CommitmentStatus.NOT_REQUIRED,
            command=command,
        )
        return _result(event)

    async def create_team(
        self, actor: Actor, team_id: UUID, command: TeamEventCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        await self._access.authorise(
            actor, team_id, command.grant_id, ManagementAction.CALENDAR
        )
        _command(command)
        event = await self._calendar.create_event(
            actor_id=actor.id,
            subject_id=actor.id,
            team_id=team_id,
            request_id=None,
            kind=CalendarEventKind.TEAM,
            commitment_status=CommitmentStatus.NOT_REQUIRED,
            command=command,
        )
        return _result(event)

    async def create_commitment(
        self, actor: Actor, team_id: UUID, command: CommitmentCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        access = await self._workspaces.require_read(actor.id, team_id)
        _require(access.unit_kind is OrganisationKind.TEAM, CalendarItemNotFound())
        await self._access.authorise(
            actor, team_id, command.grant_id, ManagementAction.CALENDAR
        )
        _command(command)
        members = await self._calendar.current_team_members(team_id)
        _require(command.subject_user_id in members, CalendarItemNotFound())
        _require(
            await self._calendar.request_belongs_to_team(command.request_id, team_id),
            CalendarItemNotFound(),
        )
        await self._access.require_no_requester_conflict(
            actor, command.request_id, command.subject_user_id
        )
        event = await self._calendar.create_event(
            actor_id=actor.id,
            subject_id=command.subject_user_id,
            team_id=team_id,
            request_id=command.request_id,
            kind=CalendarEventKind.COMMITMENT,
            commitment_status=CommitmentStatus.PENDING,
            command=command,
        )
        return _result(event)

    async def update(
        self, actor: Actor, event_id: UUID, command: CalendarEventUpdate
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._access.authorise_event_change(actor, event)
        _command(command)
        await self._calendar.replace_event(event, command)
        return _result(event)

    async def cancel(
        self, actor: Actor, event_id: UUID, command: OccurrenceCancelCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._access.authorise_event_change(actor, event)
        await self._calendar.cancel_event(event, command.reason)
        return _result(event)

    async def cancel_occurrence(
        self, actor: Actor, event_id: UUID, command: OccurrenceCancelCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._access.authorise_event_change(actor, event)
        _require_occurrence(event, command.occurrence_start)
        await self._calendar.cancel_occurrence(event, actor.id, command)
        return _result(event)

    async def edit_occurrence(
        self, actor: Actor, event_id: UUID, command: OccurrenceEditCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._access.authorise_event_change(actor, event)
        _require_occurrence(event, command.occurrence_start)
        await self._calendar.edit_occurrence(event, actor.id, command)
        return _result(event)

    async def split(
        self, actor: Actor, event_id: UUID, command: FutureSplitCommand
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._access.authorise_event_change(actor, event)
        _require(
            event.recurrence is not RecurrenceFrequency.NONE,
            InvalidCalendarChange("Only a recurring event can be split."),
        )
        _require_occurrence(event, command.split_from)
        _command(command)
        _require(
            command.starts_at >= command.split_from,
            InvalidCalendarChange(
                "The replacement series must start at the split occurrence."
            ),
        )
        replacement = await self._calendar.split_series(
            event,
            actor_id=actor.id,
            split_from=command.split_from,
            replacement=CalendarEventCommand.model_validate(command.model_dump()),
        )
        return _result(replacement)

    async def decide_commitment(
        self,
        actor: Actor,
        event_id: UUID,
        command: CommitmentDecisionCommand,
        *,
        acknowledge: bool,
    ) -> CalendarEventResult:
        self._require_staff(actor)
        event = await self._calendar.locked_event(event_id, command.expected_version)
        _require(
            event.kind is CalendarEventKind.COMMITMENT
            and event.subject_user_id == actor.id,
            CalendarItemNotFound(),
        )
        await self._access.require_no_requester_conflict(
            actor, event.request_id, event.subject_user_id
        )
        _require(
            event.commitment_status is CommitmentStatus.PENDING,
            InvalidCalendarChange("This commitment already has a response."),
        )
        if not acknowledge:
            _require(
                bool(command.reason and command.reason.strip()),
                InvalidCalendarChange("Give a reason for disputing the commitment."),
            )
        status = (
            CommitmentStatus.ACKNOWLEDGED if acknowledge else CommitmentStatus.DISPUTED
        )
        await self._calendar.set_commitment(event, status, command.reason)
        return _result(event)

    async def preview_capacity(
        self, actor: Actor, team_id: UUID, command: CapacityPreviewCommand
    ) -> CapacityPreview:
        self._require_staff(actor)
        await self._access.authorise(
            actor, team_id, command.grant_id, ManagementAction.CAPACITY
        )
        _capacity_range(command.date_from, command.date_to, command.time_zone)
        return await self._capacity.preview(
            actor_id=actor.id,
            team_id=team_id,
            date_from=command.date_from,
            date_to=command.date_to,
            time_zone=command.time_zone,
        )

    async def commit_capacity(
        self, actor: Actor, team_id: UUID, command: CapacityCommitCommand
    ) -> CapacitySnapshot:
        self._require_staff(actor)
        await self._access.authorise(
            actor, team_id, command.grant_id, ManagementAction.CAPACITY
        )
        return await self._capacity.commit(
            actor_id=actor.id, team_id=team_id, token=command.token
        )

    @staticmethod
    def _require_staff(actor: Actor) -> None:
        require_staff_context(actor, CalendarItemNotFound())
