"""Validated use cases for grant-scoped operational statistics."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mist_service.domain import Actor
from mist_service.errors import StatisticsQueryInvalid
from mist_service.schemas.statistics import (
    StatisticsDashboard,
    StatisticsScope,
)
from mist_service.services.statistics_ports import StatisticsQueryPort
from mist_service.statistics_calculations import build_statistics_dashboard

MAX_DATE_RANGE_DAYS = 366


class StatisticsService:
    def __init__(self, repository: StatisticsQueryPort) -> None:
        self._repository = repository

    async def list_scopes(self, actor: Actor) -> list[StatisticsScope]:
        return await self._repository.list_scopes(actor)

    async def dashboard(
        self,
        actor: Actor,
        *,
        scope_id: str,
        from_date: date,
        to_date: date,
        time_zone_name: str,
        selected_unit_id: UUID | None = None,
        now: datetime | None = None,
    ) -> StatisticsDashboard:
        if to_date < from_date:
            raise StatisticsQueryInvalid(
                "The end date must be on or after the start date."
            )
        if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
            raise StatisticsQueryInvalid("Statistics are limited to 366 days.")
        try:
            time_zone = ZoneInfo(time_zone_name)
        except ZoneInfoNotFoundError as error:
            raise StatisticsQueryInvalid("Select a valid IANA time zone.") from error
        start = datetime.combine(from_date, time.min, time_zone).astimezone(UTC)
        end = datetime.combine(
            to_date + timedelta(days=1), time.min, time_zone
        ).astimezone(UTC)
        effective_now = now or datetime.now(UTC)
        dataset = await self._repository.load_dataset(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            start=start,
            end=end,
            at=effective_now,
        )
        return build_statistics_dashboard(
            dataset,
            from_date=from_date,
            to_date=to_date,
            time_zone=time_zone,
            as_of_date=effective_now.astimezone(time_zone).date(),
        )
