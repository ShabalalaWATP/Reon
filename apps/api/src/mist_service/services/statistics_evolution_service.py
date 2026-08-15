"""Validated use cases for advanced grant-scoped operational statistics."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mist_service.domain import Actor
from mist_service.errors import StatisticsQueryInvalid
from mist_service.schemas.statistics_evolution import (
    StatisticsEvolution,
    StatisticsExportCommand,
    StatisticsExportResult,
)
from mist_service.services.statistics_ports import (
    StatisticsEvolutionQueryPort,
    StatisticsExportAuditPort,
)
from mist_service.statistics_evolution_calculations import (
    EXPORT_REASON,
    build_statistics_evolution,
)

MAX_DATE_RANGE_DAYS = 366


class StatisticsEvolutionService:
    def __init__(
        self,
        queries: StatisticsEvolutionQueryPort,
        export_audit: StatisticsExportAuditPort,
    ) -> None:
        self._queries = queries
        self._export_audit = export_audit

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
    ) -> StatisticsEvolution:
        time_zone = _validate_range(from_date, to_date, time_zone_name)
        effective_now = now or datetime.now(UTC)
        start = datetime.combine(from_date, time.min, time_zone).astimezone(UTC)
        end = datetime.combine(
            to_date + timedelta(days=1), time.min, time_zone
        ).astimezone(UTC)
        period_days = (to_date - from_date).days + 1
        previous_from = from_date - timedelta(days=period_days)
        previous_to = from_date - timedelta(days=1)
        previous_start = datetime.combine(
            previous_from, time.min, time_zone
        ).astimezone(UTC)
        previous_end = datetime.combine(
            previous_to + timedelta(days=1), time.min, time_zone
        ).astimezone(UTC)
        dataset = await self._queries.load(
            actor,
            scope_id=scope_id,
            selected_unit_id=selected_unit_id,
            start=start,
            end=end,
            previous_start=previous_start,
            previous_end=previous_end,
            at=effective_now,
        )
        return build_statistics_evolution(
            dataset,
            from_date=from_date,
            to_date=to_date,
            time_zone=time_zone,
            now=effective_now,
        )

    async def request_export(
        self,
        actor: Actor,
        command: StatisticsExportCommand,
        *,
        now: datetime | None = None,
    ) -> StatisticsExportResult:
        result = await self.dashboard(
            actor,
            scope_id=command.scope_id,
            selected_unit_id=command.unit_id,
            from_date=command.from_date,
            to_date=command.to_date,
            time_zone_name=command.time_zone,
            now=now,
        )
        selected_unit = getattr(result, "selected_unit", None)
        if selected_unit is None:
            raise StatisticsQueryInvalid("The statistics scope is unavailable.")
        await self._export_audit.record_denied_export(
            actor=actor,
            command=command,
            scope_unit_id=selected_unit.id,
            row_count=_visible_row_count(result),
            cohort_suppressed=_has_suppression(result),
            reason=EXPORT_REASON,
        )
        return StatisticsExportResult(
            state="PENDING",
            download_url=None,
            expires_at=None,
            message=(
                "The export was not generated. Target-environment policy approval "
                "is pending."
            ),
        )


def _validate_range(from_date: date, to_date: date, name: str) -> ZoneInfo:
    if to_date < from_date:
        raise StatisticsQueryInvalid("The end date must be on or after the start date.")
    if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
        raise StatisticsQueryInvalid("Statistics are limited to 366 days.")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise StatisticsQueryInvalid("Select a valid IANA time zone.") from error


def _visible_row_count(result: StatisticsEvolution) -> int:
    return (
        len(result.comparison)
        + len(result.bottlenecks)
        + len(result.capacity)
        + len(result.releases)
        + len(result.notifications)
        + len(result.iterations)
        + len(result.projection.periods)
    )


def _has_suppression(result: StatisticsEvolution) -> bool:
    return (
        any(item.suppressed for item in result.comparison)
        or any(item.suppressed for item in result.bottlenecks)
        or any(item.suppressed for item in result.releases)
        or any(item.suppressed for item in result.notifications)
        or any(item.suppressed for item in result.iterations)
    )
