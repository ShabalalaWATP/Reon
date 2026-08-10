"""Validated calendar commands and privacy-safe read models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from istari_service.calendar_models import (
    CalendarCategory,
    CalendarEventKind,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)

Title = Annotated[str, Field(min_length=3, max_length=160)]
Notes = Annotated[str, Field(min_length=1, max_length=2000)]
Reason = Annotated[str, Field(min_length=10, max_length=500)]


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(item.title() for item in rest)


class CalendarEventCommand(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    title: Title
    notes: Notes
    starts_at: datetime
    ends_at: datetime
    time_zone: Annotated[str, Field(min_length=1, max_length=64)]
    all_day: bool
    category: CalendarCategory
    visibility: CalendarVisibility
    recurrence: RecurrenceFrequency
    recurrence_interval: Annotated[int, Field(ge=1, le=4)]
    recurrence_until: datetime | None

    @model_validator(mode="after")
    def valid_window(self) -> CalendarEventCommand:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Calendar times require a time zone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("The event end must be after its start.")
        if self.recurrence is RecurrenceFrequency.NONE and self.recurrence_until:
            raise ValueError("A non-recurring event cannot have a recurrence end.")
        if (
            self.recurrence is not RecurrenceFrequency.NONE
            and not self.recurrence_until
        ):
            raise ValueError("A recurring event requires a recurrence end.")
        if self.recurrence_until and self.recurrence_until < self.starts_at:
            raise ValueError("The recurrence end cannot precede the first event.")
        return self


class PersonalEventCommand(CalendarEventCommand):
    pass


class TeamEventCommand(CalendarEventCommand):
    grant_id: UUID


class CommitmentCommand(TeamEventCommand):
    subject_user_id: UUID
    request_id: UUID


class CalendarEventUpdate(CalendarEventCommand):
    expected_version: Annotated[int, Field(ge=1)]


class OccurrenceCancelCommand(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    expected_version: Annotated[int, Field(ge=1)]
    occurrence_start: datetime
    reason: Reason


class OccurrenceEditCommand(OccurrenceCancelCommand):
    title: Title
    notes: Notes
    replacement_start: datetime
    replacement_end: datetime

    @model_validator(mode="after")
    def valid_replacement(self) -> OccurrenceEditCommand:
        if self.replacement_end <= self.replacement_start:
            raise ValueError("The replacement end must follow its start.")
        return self


class FutureSplitCommand(CalendarEventCommand):
    expected_version: Annotated[int, Field(ge=1)]
    split_from: datetime
    reason: Reason


class CommitmentDecisionCommand(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    expected_version: Annotated[int, Field(ge=1)]
    reason: Reason | None = None


class CalendarOccurrence(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    event_id: UUID
    occurrence_start: datetime
    starts_at: datetime
    ends_at: datetime
    title: str
    notes: str | None
    category: CalendarCategory
    visibility: CalendarVisibility
    kind: CalendarEventKind
    subject_user_id: UUID
    subject_display_name: str
    team_id: UUID | None
    request_id: UUID | None
    all_day: bool
    time_zone: str
    recurrence: RecurrenceFrequency
    commitment_status: CommitmentStatus
    version: int
    is_exception: bool


class CalendarOccurrenceList(BaseModel):
    items: list[CalendarOccurrence]


class CalendarEventResult(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    event_id: UUID
    version: int


class CapacityDay(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    date: date
    member_count: int
    baseline_minutes: int
    unavailable_minutes: int
    available_minutes: int


class CapacityPreviewCommand(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    grant_id: UUID
    date_from: date
    date_to: date
    time_zone: Annotated[str, Field(min_length=1, max_length=64)]


class CapacityPreview(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    token: str
    expires_at: datetime
    days: list[CapacityDay]


class CapacityCommitCommand(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    grant_id: UUID
    token: Annotated[str, Field(min_length=32, max_length=64)]


class CapacitySnapshot(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _camel(value), populate_by_name=True
    )

    snapshot_id: UUID
    days: list[CapacityDay]
