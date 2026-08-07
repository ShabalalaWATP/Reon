"""Bounded recurrence expansion preserving local wall-clock intent."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from istari_service.calendar_models import (
    CalendarEvent,
    CalendarOccurrenceException,
    OccurrenceExceptionKind,
    RecurrenceFrequency,
)

MAX_OCCURRENCES = 750


@dataclass(frozen=True, slots=True)
class ExpandedOccurrence:
    occurrence_start: datetime
    starts_at: datetime
    ends_at: datetime
    title: str
    notes: str
    is_exception: bool = False


def expand_event(
    event: CalendarEvent,
    exceptions: list[CalendarOccurrenceException],
    range_start: datetime,
    range_end: datetime,
) -> list[ExpandedOccurrence]:
    exception_by_start = {_utc(item.occurrence_start): item for item in exceptions}
    result: list[ExpandedOccurrence] = []
    for occurrence in _base_occurrences(event, range_end):
        exception = exception_by_start.get(occurrence.occurrence_start)
        if exception and exception.kind is OccurrenceExceptionKind.CANCELLED:
            continue
        if exception:
            occurrence = replace(
                occurrence,
                starts_at=(
                    _utc(exception.replacement_start)
                    if exception.replacement_start
                    else occurrence.starts_at
                ),
                ends_at=(
                    _utc(exception.replacement_end)
                    if exception.replacement_end
                    else occurrence.ends_at
                ),
                title=exception.title or occurrence.title,
                notes=exception.notes or occurrence.notes,
                is_exception=True,
            )
        if occurrence.ends_at > range_start and occurrence.starts_at < range_end:
            result.append(occurrence)
    return result


def _base_occurrences(
    event: CalendarEvent, range_end: datetime
) -> list[ExpandedOccurrence]:
    zone = ZoneInfo(event.time_zone)
    start_local = _utc(event.starts_at).astimezone(zone)
    end_local = _utc(event.ends_at).astimezone(zone)
    wall_duration = end_local.replace(tzinfo=None) - start_local.replace(tzinfo=None)
    step_days = _step_days(event.recurrence) * event.recurrence_interval
    output: list[ExpandedOccurrence] = []
    index = 0
    while index < MAX_OCCURRENCES:
        local_naive = start_local.replace(tzinfo=None) + timedelta(
            days=step_days * index
        )
        occurrence_start = _resolve_local(local_naive, zone, start_local.fold)
        occurrence_end = _resolve_local(
            local_naive + wall_duration, zone, end_local.fold
        )
        starts_at = occurrence_start.astimezone(UTC)
        if starts_at >= range_end:
            break
        if event.recurrence_until and starts_at > _utc(event.recurrence_until):
            break
        output.append(
            ExpandedOccurrence(
                occurrence_start=starts_at,
                starts_at=starts_at,
                ends_at=occurrence_end.astimezone(UTC),
                title=event.title,
                notes=event.notes,
            )
        )
        if event.recurrence is RecurrenceFrequency.NONE:
            break
        index += 1
    return output


def _resolve_local(value: datetime, zone: ZoneInfo, fold: int) -> datetime:
    candidate = value.replace(tzinfo=zone, fold=fold)
    round_trip = candidate.astimezone(UTC).astimezone(zone)
    if round_trip.replace(tzinfo=None) == value:
        return candidate
    return round_trip


def _step_days(frequency: RecurrenceFrequency) -> int:
    if frequency is RecurrenceFrequency.DAILY:
        return 1
    if frequency is RecurrenceFrequency.WEEKLY:
        return 7
    return 0


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
