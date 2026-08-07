"""Versioned calendar-backed team capacity previews and snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import CapacityReservation, ReservationStatus
from istari_service.calendar_models import (
    CalendarCapacityPreview,
    CalendarCapacitySnapshot,
    CalendarEventKind,
)
from istari_service.errors import InvalidCalendarChange, StaleVersion
from istari_service.operational_analytics_projection import (
    project_capacity_snapshot_facts,
)
from istari_service.repositories.calendar import SqlAlchemyCalendarRepository
from istari_service.schemas.calendar import (
    CalendarOccurrence,
    CapacityDay,
    CapacityPreview,
    CapacitySnapshot,
)

WORKDAY_MINUTES = 450
PREVIEW_TTL = timedelta(minutes=10)


class CalendarCapacityService:
    def __init__(
        self, session: AsyncSession, calendar: SqlAlchemyCalendarRepository
    ) -> None:
        self._session = session
        self._calendar = calendar

    async def preview(
        self,
        *,
        actor_id: UUID,
        team_id: UUID,
        date_from: date,
        date_to: date,
        time_zone: str,
    ) -> CapacityPreview:
        days, digest = await self._calculate(team_id, date_from, date_to, time_zone)
        now = datetime.now(UTC)
        record = CalendarCapacityPreview(
            token=token_urlsafe(32),
            team_id=team_id,
            created_by_user_id=actor_id,
            date_from=date_from,
            date_to=date_to,
            time_zone=time_zone,
            source_digest=digest,
            days=[item.model_dump(mode="json") for item in days],
            expires_at=now + PREVIEW_TTL,
        )
        self._session.add(record)
        await self._session.flush()
        return CapacityPreview(
            token=record.token, expires_at=record.expires_at, days=days
        )

    async def commit(
        self, *, actor_id: UUID, team_id: UUID, token: str
    ) -> CapacitySnapshot:
        preview = await self._session.scalar(
            select(CalendarCapacityPreview)
            .where(
                CalendarCapacityPreview.token == token,
                CalendarCapacityPreview.team_id == team_id,
                CalendarCapacityPreview.created_by_user_id == actor_id,
            )
            .with_for_update()
        )
        if preview is None or preview.consumed_at is not None:
            raise InvalidCalendarChange("This capacity preview is unavailable.")
        now = datetime.now(UTC)
        if _utc(preview.expires_at) <= now:
            raise InvalidCalendarChange("This capacity preview has expired.")
        days, digest = await self._calculate(
            team_id, preview.date_from, preview.date_to, preview.time_zone
        )
        if digest != preview.source_digest:
            raise StaleVersion("Calendar availability changed. Create a new preview.")
        preview.consumed_at = now
        snapshot = CalendarCapacitySnapshot(
            preview_id=preview.id,
            team_id=team_id,
            committed_by_user_id=actor_id,
            date_from=preview.date_from,
            date_to=preview.date_to,
            time_zone=preview.time_zone,
            source_digest=digest,
            days=[item.model_dump(mode="json") for item in days],
        )
        self._session.add(snapshot)
        await self._session.flush()
        await project_capacity_snapshot_facts(self._session, snapshot, occurred_at=now)
        return CapacitySnapshot(snapshot_id=snapshot.id, days=days)

    async def _calculate(
        self, team_id: UUID, date_from: date, date_to: date, time_zone: str
    ) -> tuple[list[CapacityDay], str]:
        zone = ZoneInfo(time_zone)
        range_start = datetime.combine(date_from, time.min, zone).astimezone(UTC)
        range_end = datetime.combine(
            date_to + timedelta(days=1), time.min, zone
        ).astimezone(UTC)
        occurrences = await self._calendar.list_team(team_id, range_start, range_end)
        reservations = list(
            await self._session.scalars(
                select(CapacityReservation).where(
                    CapacityReservation.team_id == team_id,
                    CapacityReservation.status == ReservationStatus.ACTIVE,
                    CapacityReservation.starts_at < range_end,
                    CapacityReservation.ends_at > range_start,
                )
            )
        )
        member_count = len(await self._calendar.current_team_members(team_id))
        digest = _digest(occurrences, member_count, reservations)
        output: list[CapacityDay] = []
        current = date_from
        while current <= date_to:
            baseline = WORKDAY_MINUTES * member_count if current.weekday() < 5 else 0
            unavailable = sum(
                _minutes_on_day(item.starts_at, item.ends_at, current, zone)
                * (member_count if item.kind is CalendarEventKind.TEAM else 1)
                for item in occurrences
            ) + sum(
                _minutes_on_day(item.starts_at, item.ends_at, current, zone)
                for item in reservations
            )
            unavailable = min(unavailable, baseline)
            output.append(
                CapacityDay(
                    date=current,
                    member_count=member_count,
                    baseline_minutes=baseline,
                    unavailable_minutes=unavailable,
                    available_minutes=baseline - unavailable,
                )
            )
            current += timedelta(days=1)
        return output, digest


def _minutes_on_day(start: datetime, end: datetime, day: date, zone: ZoneInfo) -> int:
    day_start = datetime.combine(day, time.min, zone).astimezone(UTC)
    day_end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    overlap = max(timedelta(), min(_utc(end), day_end) - max(_utc(start), day_start))
    return round(overlap.total_seconds() / 60)


def _digest(
    occurrences: list[CalendarOccurrence],
    member_count: int,
    reservations: Sequence[CapacityReservation] = (),
) -> str:
    parts = [str(member_count)]
    parts.extend(
        f"{item.event_id}:{item.version}:{item.occurrence_start.isoformat()}:{item.starts_at.isoformat()}:{item.ends_at.isoformat()}"
        for item in occurrences
    )
    parts.extend(
        f"reservation:{item.id}:{item.version}:{item.starts_at.isoformat()}:{item.ends_at.isoformat()}:{item.status.value}"
        for item in reservations
    )
    return sha256("|".join(parts).encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
