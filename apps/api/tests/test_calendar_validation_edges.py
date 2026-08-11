"""Boundary tests for calendar validation, recurrence and capacity arithmetic."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from istari_service.calendar_capacity import _digest, _minutes_on_day, _utc
from istari_service.calendar_models import (
    CalendarCategory,
    CalendarEvent,
    CalendarEventKind,
    CalendarOccurrenceException,
    CalendarVisibility,
    CommitmentStatus,
    OccurrenceExceptionKind,
    RecurrenceFrequency,
)
from istari_service.calendar_recurrence import expand_event
from istari_service.schemas.calendar import (
    CalendarOccurrence,
    OccurrenceEditCommand,
    PersonalEventCommand,
)
from istari_service.services.calendar_service import (
    _capacity_range,
    _command,
    _range,
    _require,
    _zone,
)


def event_payload(**updates: object) -> dict[str, object]:
    start = datetime(2026, 8, 10, 9, tzinfo=UTC)
    payload: dict[str, object] = {
        "title": "Synthetic planning block",
        "notes": "Required synthetic planning detail.",
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=2)).isoformat(),
        "timeZone": "Europe/London",
        "allDay": False,
        "category": "TRAINING",
        "visibility": "PRIVATE",
        "recurrence": "NONE",
        "recurrenceInterval": 1,
        "recurrenceUntil": None,
    }
    payload.update(updates)
    return payload


@pytest.mark.parametrize(
    "updates, message",
    [
        (
            {"startsAt": "2026-08-10T09:00:00", "endsAt": "2026-08-10T11:00:00"},
            "require a time zone",
        ),
        ({"endsAt": "2026-08-10T08:00:00Z"}, "end must be after"),
        (
            {"recurrenceUntil": "2026-08-11T09:00:00Z"},
            "non-recurring event",
        ),
        ({"recurrence": "DAILY"}, "requires a recurrence end"),
        (
            {"recurrence": "DAILY", "recurrenceUntil": "2026-08-09T09:00:00Z"},
            "cannot precede",
        ),
    ],
)
def test_event_schema_rejects_each_invalid_window_branch(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        PersonalEventCommand.model_validate(event_payload(**updates))


def test_occurrence_edit_requires_a_positive_replacement_window() -> None:
    with pytest.raises(ValidationError, match="replacement end must follow"):
        OccurrenceEditCommand.model_validate(
            {
                "expectedVersion": 1,
                "occurrenceStart": "2026-08-10T09:00:00Z",
                "reason": "Required synthetic rescheduling reason.",
                "title": "Changed planning block",
                "notes": "Required changed detail.",
                "replacementStart": "2026-08-10T12:00:00Z",
                "replacementEnd": "2026-08-10T11:00:00Z",
            }
        )


def test_service_validators_cover_valid_and_invalid_bounds() -> None:
    command = PersonalEventCommand.model_validate(event_payload())
    _command(command)
    _range(command.starts_at, command.ends_at)
    _capacity_range(date(2026, 8, 10), date(2026, 8, 10), "Europe/London")
    _zone("Europe/London")
    _require(True, RuntimeError("not raised"))

    invalid = PersonalEventCommand.model_validate(
        event_payload(
            recurrence="DAILY",
            recurrenceUntil="2027-08-12T09:00:00Z",
        )
    )
    with pytest.raises(Exception, match="366 days"):
        _command(invalid)
    with pytest.raises(Exception, match="range is invalid"):
        _range(command.ends_at, command.starts_at)
    with pytest.raises(Exception, match="limited to 366"):
        _range(command.starts_at, command.starts_at + timedelta(days=367))
    with pytest.raises(Exception, match="91 days"):
        _capacity_range(date(2026, 8, 10), date(2026, 11, 10), "Europe/London")
    with pytest.raises(Exception, match="IANA"):
        _zone("Not/AZone")
    with pytest.raises(RuntimeError, match="raised"):
        _require(False, RuntimeError("raised"))


def test_recurrence_applies_optional_exceptions_and_dst_gap_resolution() -> None:
    user_id = uuid4()
    event = calendar_event(
        user_id,
        start=datetime(2026, 3, 28, 1, 30, tzinfo=UTC),
        recurrence=RecurrenceFrequency.DAILY,
        until=datetime(2026, 3, 30, 1, 30, tzinfo=UTC),
    )
    first = event.starts_at
    second = datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    exceptions = [
        CalendarOccurrenceException(
            event_id=event.id,
            occurrence_start=first,
            kind=OccurrenceExceptionKind.CANCELLED,
            reason="Required cancellation reason.",
            changed_by_user_id=user_id,
        ),
        CalendarOccurrenceException(
            event_id=event.id,
            occurrence_start=second,
            kind=OccurrenceExceptionKind.EDITED,
            replacement_start=None,
            replacement_end=None,
            title="DST adjusted block",
            notes=None,
            reason="Required DST adjustment reason.",
            changed_by_user_id=user_id,
        ),
    ]
    expanded = expand_event(
        event,
        exceptions,
        datetime(2026, 3, 27, tzinfo=UTC),
        datetime(2026, 4, 1, tzinfo=UTC),
    )
    assert expanded[0].title == "DST adjusted block"
    assert expanded[0].notes == event.notes
    assert expanded[0].is_exception is True
    assert expanded[0].starts_at == second

    weekly = calendar_event(
        user_id,
        start=datetime(2026, 4, 1, 9, tzinfo=UTC).replace(tzinfo=None),
        recurrence=RecurrenceFrequency.WEEKLY,
        until=datetime(2026, 4, 15, 9, tzinfo=UTC).replace(tzinfo=None),
    )
    assert (
        len(
            expand_event(
                weekly,
                [],
                datetime(2026, 4, 1, tzinfo=UTC),
                datetime(2026, 4, 16, tzinfo=UTC),
            )
        )
        == 3
    )


def test_recurrence_expansion_obeys_its_hard_safety_limit(monkeypatch) -> None:
    monkeypatch.setattr("istari_service.calendar_recurrence.MAX_OCCURRENCES", 1)
    event = calendar_event(
        uuid4(),
        start=datetime(2026, 4, 1, 9, tzinfo=UTC),
        recurrence=RecurrenceFrequency.DAILY,
        until=datetime(2026, 4, 20, 9, tzinfo=UTC),
    )
    expanded = expand_event(
        event,
        [],
        datetime(2026, 4, 1, tzinfo=UTC),
        datetime(2026, 4, 20, tzinfo=UTC),
    )
    assert len(expanded) == 1


def test_capacity_helpers_clip_overlap_and_version_the_source() -> None:
    zone = ZoneInfo("Europe/London")
    day = date(2026, 8, 10)
    assert (
        _minutes_on_day(
            datetime(2026, 8, 9, 23, tzinfo=UTC),
            datetime(2026, 8, 10, 2, tzinfo=UTC),
            day,
            zone,
        )
        == 180
    )
    assert (
        _minutes_on_day(
            datetime(2026, 8, 11, 9, tzinfo=UTC),
            datetime(2026, 8, 11, 10, tzinfo=UTC),
            day,
            zone,
        )
        == 0
    )
    naive = datetime(2026, 8, 10, 9, tzinfo=UTC).replace(tzinfo=None)
    assert _utc(naive).tzinfo is UTC
    occurrence = CalendarOccurrence(
        eventId=uuid4(),
        occurrenceStart="2026-08-10T09:00:00Z",
        startsAt="2026-08-10T09:00:00Z",
        endsAt="2026-08-10T10:00:00Z",
        title="Busy",
        notes=None,
        category="AVAILABILITY",
        visibility="PRIVATE",
        kind="PERSONAL",
        subjectUserId=uuid4(),
        subjectDisplayName="Synthetic User",
        teamId=None,
        requestId=None,
        allDay=False,
        timeZone="Europe/London",
        recurrence="NONE",
        commitmentStatus="NOT_REQUIRED",
        version=1,
        isException=False,
    )
    assert _digest([], 0) != _digest([occurrence], 1)


def calendar_event(
    user_id: UUID,
    *,
    start: datetime,
    recurrence: RecurrenceFrequency,
    until: datetime,
) -> CalendarEvent:
    event = CalendarEvent(
        subject_user_id=user_id,
        team_id=None,
        created_by_user_id=user_id,
        kind=CalendarEventKind.PERSONAL,
        category=CalendarCategory.TRAINING,
        visibility=CalendarVisibility.PRIVATE,
        title="Protected recurring block",
        notes="Required recurring detail.",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        time_zone="Europe/London",
        all_day=False,
        recurrence=recurrence,
        recurrence_interval=1,
        recurrence_until=until,
        commitment_status=CommitmentStatus.NOT_REQUIRED,
        version=1,
    )
    event.id = uuid4()
    return event
