"""Persistence adapter for canonical calendar events and occurrences."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.calendar_models import (
    CalendarCategory,
    CalendarEvent,
    CalendarEventKind,
    CalendarEventStatus,
    CalendarOccurrenceException,
    CalendarVisibility,
    CommitmentStatus,
    OccurrenceExceptionKind,
    RecurrenceFrequency,
)
from istari_service.calendar_recurrence import ExpandedOccurrence, expand_event
from istari_service.errors import (
    CalendarItemNotFound,
    InvalidCalendarChange,
    StaleVersion,
)
from istari_service.models import User
from istari_service.schemas.calendar import (
    CalendarEventCommand,
    CalendarOccurrence,
    OccurrenceCancelCommand,
    OccurrenceEditCommand,
)
from istari_service.team_models import TeamMembership


class SqlAlchemyCalendarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_team_ids(self, user_id: UUID) -> list[UUID]:
        now = datetime.now(UTC)
        return list(
            await self.session.scalars(
                select(TeamMembership.team_id).where(
                    TeamMembership.user_id == user_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                )
            )
        )

    async def current_team_members(self, team_id: UUID) -> set[UUID]:
        now = datetime.now(UTC)
        return set(
            await self.session.scalars(
                select(TeamMembership.user_id).where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                )
            )
        )

    async def list_personal(
        self, user_id: UUID, range_start: datetime, range_end: datetime
    ) -> list[CalendarOccurrence]:
        team_ids = await self.current_team_ids(user_id)
        events = list(
            await self.session.scalars(
                self._window_query(range_start, range_end).where(
                    or_(
                        CalendarEvent.subject_user_id == user_id,
                        CalendarEvent.team_id.in_(team_ids),
                    )
                )
            )
        )
        return await self._expand(events, range_start, range_end, viewer_id=user_id)

    async def list_team(
        self, team_id: UUID, range_start: datetime, range_end: datetime
    ) -> list[CalendarOccurrence]:
        member_ids = await self.current_team_members(team_id)
        events = list(
            await self.session.scalars(
                self._window_query(range_start, range_end).where(
                    or_(
                        CalendarEvent.team_id == team_id,
                        CalendarEvent.subject_user_id.in_(member_ids),
                    )
                )
            )
        )
        return await self._expand(events, range_start, range_end, viewer_id=None)

    async def create_event(
        self,
        *,
        actor_id: UUID,
        subject_id: UUID,
        team_id: UUID | None,
        kind: CalendarEventKind,
        commitment_status: CommitmentStatus,
        command: CalendarEventCommand,
    ) -> CalendarEvent:
        event = CalendarEvent(
            subject_user_id=subject_id,
            team_id=team_id,
            created_by_user_id=actor_id,
            kind=kind,
            status=CalendarEventStatus.ACTIVE,
            commitment_status=commitment_status,
            commitment_reason=None,
            version=1,
            **CalendarEventCommand.model_validate(command.model_dump()).model_dump(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def locked_event(
        self, event_id: UUID, expected_version: int
    ) -> CalendarEvent:
        event = await self.session.scalar(
            select(CalendarEvent).where(CalendarEvent.id == event_id).with_for_update()
        )
        if event is None:
            raise CalendarItemNotFound()
        if event.version != expected_version:
            raise StaleVersion()
        if event.status is CalendarEventStatus.CANCELLED:
            raise InvalidCalendarChange("This calendar event is cancelled.")
        return event

    async def replace_event(
        self, event: CalendarEvent, command: CalendarEventCommand
    ) -> CalendarEvent:
        values = CalendarEventCommand.model_validate(command.model_dump()).model_dump()
        for field, value in values.items():
            setattr(event, field, value)
        event.version += 1
        return event

    async def cancel_event(self, event: CalendarEvent, reason: str) -> CalendarEvent:
        event.status = CalendarEventStatus.CANCELLED
        event.commitment_reason = reason.strip()
        event.version += 1
        return event

    async def cancel_occurrence(
        self, event: CalendarEvent, actor_id: UUID, command: OccurrenceCancelCommand
    ) -> CalendarEvent:
        await self._require_new_exception(event.id, command.occurrence_start)
        self.session.add(
            CalendarOccurrenceException(
                event_id=event.id,
                occurrence_start=command.occurrence_start,
                kind=OccurrenceExceptionKind.CANCELLED,
                reason=command.reason.strip(),
                changed_by_user_id=actor_id,
            )
        )
        event.version += 1
        return event

    async def edit_occurrence(
        self, event: CalendarEvent, actor_id: UUID, command: OccurrenceEditCommand
    ) -> CalendarEvent:
        await self._require_new_exception(event.id, command.occurrence_start)
        self.session.add(
            CalendarOccurrenceException(
                event_id=event.id,
                occurrence_start=command.occurrence_start,
                kind=OccurrenceExceptionKind.EDITED,
                replacement_start=command.replacement_start,
                replacement_end=command.replacement_end,
                title=command.title.strip(),
                notes=command.notes.strip(),
                reason=command.reason.strip(),
                changed_by_user_id=actor_id,
            )
        )
        event.version += 1
        return event

    async def set_commitment(
        self, event: CalendarEvent, status: CommitmentStatus, reason: str | None
    ) -> CalendarEvent:
        event.commitment_status = status
        event.commitment_reason = reason.strip() if reason else None
        event.version += 1
        return event

    def _window_query(
        self, start: datetime, end: datetime
    ) -> Select[tuple[CalendarEvent]]:
        return (
            select(CalendarEvent)
            .where(
                CalendarEvent.status == CalendarEventStatus.ACTIVE,
                CalendarEvent.starts_at < end,
                or_(
                    CalendarEvent.ends_at > start,
                    CalendarEvent.recurrence != RecurrenceFrequency.NONE,
                ),
                or_(
                    CalendarEvent.recurrence_until.is_(None),
                    CalendarEvent.recurrence_until >= start,
                ),
            )
            .order_by(CalendarEvent.starts_at, CalendarEvent.id)
            .limit(500)
        )

    async def _expand(
        self,
        events: list[CalendarEvent],
        start: datetime,
        end: datetime,
        *,
        viewer_id: UUID | None,
    ) -> list[CalendarOccurrence]:
        exceptions = await self._exceptions(events)
        names = await self._names(events)
        output: list[CalendarOccurrence] = []
        for event in events:
            reveal = (
                viewer_id == event.subject_user_id
                or event.kind is CalendarEventKind.TEAM
            )
            for occurrence in expand_event(event, exceptions[event.id], start, end):
                output.append(
                    _view(event, occurrence, names[event.subject_user_id], reveal)
                )
        return sorted(output, key=lambda item: (item.starts_at, str(item.event_id)))

    async def _exceptions(
        self, events: list[CalendarEvent]
    ) -> dict[UUID, list[CalendarOccurrenceException]]:
        grouped: dict[UUID, list[CalendarOccurrenceException]] = defaultdict(list)
        if not events:
            return grouped
        rows = await self.session.scalars(
            select(CalendarOccurrenceException).where(
                CalendarOccurrenceException.event_id.in_([item.id for item in events])
            )
        )
        for item in rows:
            grouped[item.event_id].append(item)
        return grouped

    async def _names(self, events: list[CalendarEvent]) -> dict[UUID, str]:
        if not events:
            return {}
        rows = (
            await self.session.execute(
                select(User.id, User.display_name).where(
                    User.id.in_({item.subject_user_id for item in events})
                )
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _require_new_exception(
        self, event_id: UUID, occurrence: datetime
    ) -> None:
        existing = await self.session.scalar(
            select(CalendarOccurrenceException.id).where(
                CalendarOccurrenceException.event_id == event_id,
                CalendarOccurrenceException.occurrence_start == occurrence,
            )
        )
        if existing:
            raise InvalidCalendarChange("This occurrence already has an exception.")


def _view(
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
        all_day=event.all_day,
        time_zone=event.time_zone,
        recurrence=event.recurrence,
        commitment_status=event.commitment_status,
        version=event.version,
        is_exception=occurrence.is_exception,
    )
