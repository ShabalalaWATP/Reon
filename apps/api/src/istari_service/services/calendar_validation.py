"""Pure calendar validation and projection helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from istari_service.calendar_ports import CalendarEventRecord
from istari_service.calendar_recurrence import expand_event
from istari_service.errors import InvalidCalendarChange
from istari_service.schemas.calendar import CalendarEventCommand, CalendarEventResult


def validate_command(command: CalendarEventCommand) -> None:
    validate_zone(command.time_zone)
    if command.recurrence_until:
        require(
            command.recurrence_until <= command.starts_at + timedelta(days=366),
            InvalidCalendarChange("Recurring series are limited to 366 days."),
        )


def validate_range(start: datetime, end: datetime) -> None:
    require(
        start.tzinfo is not None and end.tzinfo is not None and start < end,
        InvalidCalendarChange("The calendar range is invalid."),
    )
    require(
        end - start <= timedelta(days=366),
        InvalidCalendarChange("Calendar ranges are limited to 366 days."),
    )


def validate_capacity_range(start: date, end: date, zone: str) -> None:
    validate_zone(zone)
    require(
        start <= end and (end - start).days <= 90,
        InvalidCalendarChange("Capacity ranges are limited to 91 days."),
    )


def require_occurrence(event: CalendarEventRecord, occurrence: datetime) -> None:
    found = expand_event(
        cast(Any, event),
        [],
        occurrence - timedelta(seconds=1),
        occurrence + timedelta(seconds=1),
    )
    require(
        any(item.occurrence_start == occurrence for item in found),
        InvalidCalendarChange("Select an occurrence from this series."),
    )


def validate_zone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise InvalidCalendarChange("Select a valid IANA time zone.") from error


def result(event: CalendarEventRecord) -> CalendarEventResult:
    return CalendarEventResult(event_id=event.id, version=event.version)


def require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
