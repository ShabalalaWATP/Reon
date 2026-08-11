"""Calendar use cases with final-boundary scope and lifecycle checks."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from istari_service.calendar_capacity import CalendarCapacityService
from istari_service.calendar_models import (
    CalendarEvent,
    CalendarEventKind,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)
from istari_service.calendar_recurrence import expand_event
from istari_service.domain import Actor
from istari_service.errors import (
    CalendarItemNotFound,
    InvalidCalendarChange,
    TeamWorkspaceNotFound,
)
from istari_service.management_models import ManagementAction
from istari_service.organisation_models import OrganisationKind
from istari_service.repositories.calendar import SqlAlchemyCalendarRepository
from istari_service.repositories.management import resolve_management_scope
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.calendar import (
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


class CalendarService:
    def __init__(
        self,
        calendar: SqlAlchemyCalendarRepository,
        workspaces: SqlAlchemyTeamWorkspaceRepository,
    ) -> None:
        self._calendar = calendar
        self._workspaces = workspaces
        self._capacity = CalendarCapacityService(calendar.session, calendar)

    async def personal(
        self, actor: Actor, start: datetime, end: datetime
    ) -> list[CalendarOccurrence]:
        _range(start, end)
        return await self._calendar.list_personal(actor.id, start, end)

    async def team(
        self, actor: Actor, team_id: UUID, start: datetime, end: datetime
    ) -> list[CalendarOccurrence]:
        _range(start, end)
        await self._workspaces.require_read(actor.id, team_id)
        return await self._calendar.list_team(team_id, start, end)

    async def create_personal(
        self, actor: Actor, command: PersonalEventCommand
    ) -> CalendarEventResult:
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
        await self._authorise(
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
        access = await self._workspaces.require_read(actor.id, team_id)
        _require(access.unit_kind is OrganisationKind.TEAM, CalendarItemNotFound())
        await self._authorise(
            actor, team_id, command.grant_id, ManagementAction.CALENDAR
        )
        _command(command)
        members = await self._calendar.current_team_members(team_id)
        _require(command.subject_user_id in members, CalendarItemNotFound())
        _require(
            await self._calendar.request_belongs_to_team(command.request_id, team_id),
            CalendarItemNotFound(),
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
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._authorise_event_change(actor, event)
        _command(command)
        await self._calendar.replace_event(event, command)
        return _result(event)

    async def cancel(
        self, actor: Actor, event_id: UUID, command: OccurrenceCancelCommand
    ) -> CalendarEventResult:
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._authorise_event_change(actor, event)
        await self._calendar.cancel_event(event, command.reason)
        return _result(event)

    async def cancel_occurrence(
        self, actor: Actor, event_id: UUID, command: OccurrenceCancelCommand
    ) -> CalendarEventResult:
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._authorise_event_change(actor, event)
        _require_occurrence(event, command.occurrence_start)
        await self._calendar.cancel_occurrence(event, actor.id, command)
        return _result(event)

    async def edit_occurrence(
        self, actor: Actor, event_id: UUID, command: OccurrenceEditCommand
    ) -> CalendarEventResult:
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._authorise_event_change(actor, event)
        _require_occurrence(event, command.occurrence_start)
        await self._calendar.edit_occurrence(event, actor.id, command)
        return _result(event)

    async def split(
        self, actor: Actor, event_id: UUID, command: FutureSplitCommand
    ) -> CalendarEventResult:
        event = await self._calendar.locked_event(event_id, command.expected_version)
        await self._authorise_event_change(actor, event)
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
        event.recurrence_until = command.split_from - timedelta(microseconds=1)
        event.version += 1
        replacement = await self._calendar.create_event(
            actor_id=actor.id,
            subject_id=event.subject_user_id,
            team_id=event.team_id,
            request_id=event.request_id,
            kind=event.kind,
            commitment_status=event.commitment_status,
            command=CalendarEventCommand.model_validate(command.model_dump()),
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
        event = await self._calendar.locked_event(event_id, command.expected_version)
        _require(
            event.kind is CalendarEventKind.COMMITMENT
            and event.subject_user_id == actor.id,
            CalendarItemNotFound(),
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
        await self._authorise(
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
        await self._authorise(
            actor, team_id, command.grant_id, ManagementAction.CAPACITY
        )
        return await self._capacity.commit(
            actor_id=actor.id, team_id=team_id, token=command.token
        )

    async def _authorise_event_change(self, actor: Actor, event: CalendarEvent) -> None:
        if (
            event.kind is CalendarEventKind.PERSONAL
            and event.subject_user_id == actor.id
        ):
            return
        if event.team_id is None:
            raise CalendarItemNotFound()
        access = await self._workspaces.require_read(actor.id, event.team_id)
        if (
            access.grant_id is None
            or ManagementAction.CALENDAR not in access.permissions
        ):
            raise CalendarItemNotFound()
        await self._authorise(
            actor, event.team_id, access.grant_id, ManagementAction.CALENDAR
        )

    async def _authorise(
        self, actor: Actor, team_id: UUID, grant_id: UUID, action: ManagementAction
    ) -> None:
        scope = await resolve_management_scope(
            self._calendar.session,
            subject_user_id=actor.id,
            grant_id=grant_id,
            target_unit_id=team_id,
            action=action,
            lock=True,
        )
        _require(
            scope is not None and scope.root_unit_id == team_id, TeamWorkspaceNotFound()
        )


def _command(command: CalendarEventCommand) -> None:
    _zone(command.time_zone)
    if command.recurrence_until:
        _require(
            command.recurrence_until <= command.starts_at + timedelta(days=366),
            InvalidCalendarChange("Recurring series are limited to 366 days."),
        )


def _range(start: datetime, end: datetime) -> None:
    _require(
        start.tzinfo is not None and end.tzinfo is not None and start < end,
        InvalidCalendarChange("The calendar range is invalid."),
    )
    _require(
        end - start <= timedelta(days=366),
        InvalidCalendarChange("Calendar ranges are limited to 366 days."),
    )


def _capacity_range(start: date, end: date, zone: str) -> None:
    _zone(zone)
    _require(
        start <= end and (end - start).days <= 90,
        InvalidCalendarChange("Capacity ranges are limited to 91 days."),
    )


def _require_occurrence(event: CalendarEvent, occurrence: datetime) -> None:
    found = expand_event(
        event, [], occurrence - timedelta(seconds=1), occurrence + timedelta(seconds=1)
    )
    _require(
        any(item.occurrence_start == occurrence for item in found),
        InvalidCalendarChange("Select an occurrence from this series."),
    )


def _zone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise InvalidCalendarChange("Select a valid IANA time zone.") from error


def _result(event: CalendarEvent) -> CalendarEventResult:
    return CalendarEventResult(event_id=event.id, version=event.version)


def _require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
