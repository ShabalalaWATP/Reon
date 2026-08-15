"""Neutral application contracts for calendar use cases."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from mist_service.calendar_models import (
    CalendarCategory,
    CalendarEventKind,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)
from mist_service.domain import Actor
from mist_service.management_models import ManagementAction
from mist_service.schemas.calendar import (
    CalendarEventCommand,
    CalendarOccurrence,
    CapacityPreview,
    CapacitySnapshot,
    OccurrenceCancelCommand,
    OccurrenceEditCommand,
)


class CalendarEventRecord(Protocol):
    id: UUID
    subject_user_id: UUID
    team_id: UUID | None
    request_id: UUID | None
    kind: CalendarEventKind
    category: CalendarCategory
    visibility: CalendarVisibility
    title: str
    notes: str
    starts_at: datetime
    ends_at: datetime
    time_zone: str
    recurrence_interval: int
    commitment_status: CommitmentStatus
    recurrence: RecurrenceFrequency
    recurrence_until: datetime | None
    version: int


class CalendarReadPort(Protocol):
    async def list_personal(
        self, user_id: UUID, range_start: datetime, range_end: datetime
    ) -> list[CalendarOccurrence]: ...

    async def list_team(
        self, team_id: UUID, range_start: datetime, range_end: datetime
    ) -> list[CalendarOccurrence]: ...


class CalendarEventPort(Protocol):
    async def create_event(
        self,
        *,
        actor_id: UUID,
        subject_id: UUID,
        team_id: UUID | None,
        request_id: UUID | None,
        kind: CalendarEventKind,
        commitment_status: CommitmentStatus,
        command: CalendarEventCommand,
    ) -> CalendarEventRecord: ...

    async def locked_event(
        self, event_id: UUID, expected_version: int
    ) -> CalendarEventRecord: ...

    async def replace_event(
        self, event: CalendarEventRecord, command: CalendarEventCommand
    ) -> CalendarEventRecord: ...

    async def cancel_event(
        self, event: CalendarEventRecord, reason: str
    ) -> CalendarEventRecord: ...

    async def cancel_occurrence(
        self,
        event: CalendarEventRecord,
        actor_id: UUID,
        command: OccurrenceCancelCommand,
    ) -> CalendarEventRecord: ...

    async def edit_occurrence(
        self,
        event: CalendarEventRecord,
        actor_id: UUID,
        command: OccurrenceEditCommand,
    ) -> CalendarEventRecord: ...

    async def split_series(
        self,
        event: CalendarEventRecord,
        *,
        actor_id: UUID,
        split_from: datetime,
        replacement: CalendarEventCommand,
    ) -> CalendarEventRecord: ...

    async def set_commitment(
        self,
        event: CalendarEventRecord,
        status: CommitmentStatus,
        reason: str | None,
    ) -> CalendarEventRecord: ...


class CalendarIdentityPort(Protocol):
    async def current_team_members(self, team_id: UUID) -> set[UUID]: ...

    async def request_belongs_to_team(
        self, request_id: UUID, team_id: UUID
    ) -> bool: ...

    async def request_requester_id(self, request_id: UUID) -> UUID | None: ...


class CalendarCapacityPort(Protocol):
    async def preview(
        self,
        *,
        actor_id: UUID,
        team_id: UUID,
        date_from: date,
        date_to: date,
        time_zone: str,
    ) -> CapacityPreview: ...

    async def commit(
        self, *, actor_id: UUID, team_id: UUID, token: str
    ) -> CapacitySnapshot: ...


class CalendarManagementPort(Protocol):
    async def has_authority(
        self,
        actor: Actor,
        team_id: UUID,
        grant_id: UUID,
        action: ManagementAction,
    ) -> bool: ...


class CalendarRepositoryPort(
    CalendarReadPort,
    CalendarEventPort,
    CalendarIdentityPort,
    Protocol,
):
    """Composition-facing union implemented by the calendar adapter."""
