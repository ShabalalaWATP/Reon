"""Privacy-preserving projection of persisted calendar occurrences."""

from __future__ import annotations

from mist_service.calendar_models import (
    CalendarCategory,
    CalendarEvent,
    CalendarVisibility,
)
from mist_service.calendar_recurrence import ExpandedOccurrence
from mist_service.schemas.calendar import CalendarOccurrence


def occurrence_view(
    event: CalendarEvent,
    occurrence: ExpandedOccurrence,
    display_name: str,
    reveal: bool,
) -> CalendarOccurrence:
    show_detail = reveal or event.visibility is CalendarVisibility.TEAM_DETAIL
    return CalendarOccurrence(
        event_id=event.id,
        occurrence_start=occurrence.occurrence_start,
        starts_at=occurrence.starts_at,
        ends_at=occurrence.ends_at,
        title=occurrence.title if show_detail else "Busy",
        notes=occurrence.notes if show_detail else None,
        category=event.category if show_detail else CalendarCategory.AVAILABILITY,
        visibility=event.visibility,
        kind=event.kind,
        subject_user_id=event.subject_user_id,
        subject_display_name=display_name,
        team_id=event.team_id,
        request_id=event.request_id,
        all_day=event.all_day,
        time_zone=event.time_zone,
        recurrence=event.recurrence,
        commitment_status=event.commitment_status,
        version=event.version,
        is_exception=occurrence.is_exception,
    )
