"""Aggregate calendar capacity calculations without private calendar details."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import CapacityReservation, ReservationStatus
from istari_service.calendar_models import CalendarEventKind
from istari_service.repositories.calendar import SqlAlchemyCalendarRepository
from istari_service.schemas.calendar import CalendarOccurrence

WORKDAY_MINUTES = 450


@dataclass(frozen=True, slots=True)
class PlanningCapacityDay:
    date: date
    baseline_minutes: int
    calendar_minutes: int
    reserved_minutes: int
    available_minutes: int


@dataclass(frozen=True, slots=True)
class PlanningCapacityProjection:
    days: tuple[PlanningCapacityDay, ...]
    source_digest: str

    @property
    def available_minutes(self) -> int:
        return sum(day.available_minutes for day in self.days)

    @property
    def reserved_minutes(self) -> int:
        return sum(day.reserved_minutes for day in self.days)


async def calculate_planning_capacity(
    session: AsyncSession,
    *,
    team_id: UUID,
    date_from: date,
    date_to: date,
    time_zone_name: str = "Europe/London",
) -> PlanningCapacityProjection:
    """Combine current membership, canonical events and active reservations."""

    time_zone = ZoneInfo(time_zone_name)
    range_start = datetime.combine(date_from, time.min, time_zone).astimezone(UTC)
    range_end = datetime.combine(
        date_to + timedelta(days=1), time.min, time_zone
    ).astimezone(UTC)
    calendar = SqlAlchemyCalendarRepository(session)
    occurrences = await calendar.list_team(team_id, range_start, range_end)
    reservations = tuple(
        await session.scalars(
            select(CapacityReservation).where(
                CapacityReservation.team_id == team_id,
                CapacityReservation.status == ReservationStatus.ACTIVE,
                CapacityReservation.starts_at < range_end,
                CapacityReservation.ends_at > range_start,
            )
        )
    )
    member_ids = await calendar.current_team_members(team_id)
    member_count = len(member_ids)
    days: list[PlanningCapacityDay] = []
    current = date_from
    while current <= date_to:
        baseline = WORKDAY_MINUTES * member_count if current.weekday() < 5 else 0
        calendar_minutes = sum(
            _minutes_on_day(item.starts_at, item.ends_at, current, time_zone)
            * (member_count if item.kind is CalendarEventKind.TEAM else 1)
            for item in occurrences
        )
        reserved_minutes = sum(
            _minutes_on_day(item.starts_at, item.ends_at, current, time_zone)
            for item in reservations
        )
        unavailable = min(baseline, calendar_minutes + reserved_minutes)
        days.append(
            PlanningCapacityDay(
                date=current,
                baseline_minutes=baseline,
                calendar_minutes=min(calendar_minutes, baseline),
                reserved_minutes=min(reserved_minutes, baseline),
                available_minutes=baseline - unavailable,
            )
        )
        current += timedelta(days=1)
    return PlanningCapacityProjection(
        days=tuple(days),
        source_digest=_digest(occurrences, reservations, member_ids),
    )


def _minutes_on_day(
    starts_at: datetime,
    ends_at: datetime,
    day: date,
    time_zone: ZoneInfo,
) -> int:
    day_start = datetime.combine(day, time.min, time_zone).astimezone(UTC)
    day_end = datetime.combine(day + timedelta(days=1), time.min, time_zone).astimezone(
        UTC
    )
    start = starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=UTC)
    end = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=UTC)
    overlap = max(timedelta(), min(end, day_end) - max(start, day_start))
    return round(overlap.total_seconds() / 60)


def _digest(
    occurrences: list[CalendarOccurrence],
    reservations: tuple[CapacityReservation, ...],
    member_ids: set[UUID],
) -> str:
    parts = [f"member:{item}" for item in sorted(member_ids, key=str)]
    parts.extend(
        f"event:{item.event_id}:{item.version}:{item.starts_at}:{item.ends_at}"
        for item in sorted(
            occurrences,
            key=lambda value: (
                str(value.event_id),
                value.occurrence_start,
                value.starts_at,
            ),
        )
    )
    parts.extend(
        f"reservation:{item.id}:{item.version}:{item.starts_at}:{item.ends_at}"
        for item in sorted(reservations, key=lambda value: str(value.id))
    )
    return sha256("|".join(parts).encode()).hexdigest()
