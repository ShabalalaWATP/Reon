"""Pure, cohort-safe calculations over content-free evolution facts."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from math import ceil
from statistics import median
from zoneinfo import ZoneInfo

from mist_service.analytics_models import ProjectionHealth
from mist_service.models import RequestStatus
from mist_service.schemas.statistics import ProjectionFreshness, StatisticsRange
from mist_service.schemas.statistics_evolution import (
    BottleneckMeasure,
    DemandCapacityProjection,
    ExportPolicies,
    ExportPolicy,
    PeriodComparison,
    StatisticsEvolution,
)
from mist_service.statistics_operational_calculations import (
    capacity_rows,
    demand_projection,
    iteration_rows,
    notification_rows,
    release_rows,
)
from mist_service.statistics_records import (
    StatisticsDataset,
    StatisticsEvolutionDataset,
    StatisticsStageInterval,
)

MIN_COHORT = 5
TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}
STATUS_LABELS = {
    status: status.value.replace("_", " ").title() for status in RequestStatus
}
EXPORT_REASON = (
    "Aggregate exports are disabled until the target-environment owner "
    "approves CSV and accessible PDF policy."
)


def build_statistics_evolution(
    dataset: StatisticsEvolutionDataset,
    *,
    from_date: date,
    to_date: date,
    time_zone: ZoneInfo,
    now: datetime,
) -> StatisticsEvolution:
    current = dataset.current
    common = {
        "scope": current.scope,
        "selected_unit": current.selected_unit,
        "breadcrumb": list(current.breadcrumb),
        "range": StatisticsRange(
            from_date=from_date,
            to_date=to_date,
            time_zone=time_zone.key,
            as_of_date=now.astimezone(time_zone).date(),
        ),
        "freshness": _freshness(current),
    }
    exports = ExportPolicies(
        csv=ExportPolicy(state="DENIED", reason=EXPORT_REASON),
        pdf=ExportPolicy(state="DENIED", reason=EXPORT_REASON),
    )
    if current.scope.kind == "PLATFORM" and current.selected_unit.depth == 0:
        return StatisticsEvolution(
            **common,
            comparison=[],
            bottlenecks=[],
            capacity=[],
            releases=[],
            notifications=[],
            iterations=[],
            projection=DemandCapacityProjection(
                label="Whole-platform health only; operational estimates are hidden.",
                periods=[],
            ),
            exports=exports,
        )
    capacity = capacity_rows(dataset.operational_facts, time_zone)
    return StatisticsEvolution(
        **common,
        comparison=_comparison_rows(current, dataset.previous),
        bottlenecks=_bottleneck_rows(current, now),
        capacity=capacity,
        releases=release_rows(dataset.operational_facts),
        notifications=notification_rows(dataset.operational_facts),
        iterations=iteration_rows(dataset.operational_facts),
        projection=demand_projection(current, capacity, from_date, to_date),
        exports=exports,
    )


def _freshness(dataset: StatisticsDataset) -> ProjectionFreshness:
    state = dataset.freshness
    return ProjectionFreshness(
        health=state.health if state else ProjectionHealth.DEGRADED,
        last_projected_at=state.last_projected_at if state else None,
        source_event_count=state.source_event_count if state else 0,
        projected_request_count=state.projected_request_count if state else 0,
    )


def _comparison_rows(
    current: StatisticsDataset, previous: StatisticsDataset
) -> list[PeriodComparison]:
    current_values = _request_counts(current)
    previous_values = _request_counts(previous)
    suppressed = (
        current_values["received"] < MIN_COHORT
        or previous_values["received"] < MIN_COHORT
    )
    definitions = (
        ("received", "Received", "count"),
        ("completed", "Completed cohort", "count"),
        ("active", "Active cohort", "count"),
        ("completion", "Completion rate", "percentage"),
    )
    return [
        PeriodComparison(
            key=key,
            label=label,
            current=None if suppressed else current_values[key],
            previous=None if suppressed else previous_values[key],
            change=(
                None
                if suppressed
                else round(current_values[key] - previous_values[key], 2)
            ),
            unit=unit,
            suppressed=suppressed,
        )
        for key, label, unit in definitions
    ]


def _request_counts(dataset: StatisticsDataset) -> dict[str, int | float]:
    received = len(dataset.facts)
    completed = sum(
        fact.current_status is RequestStatus.COMPLETED for fact in dataset.facts
    )
    active = sum(fact.current_status not in TERMINAL_STATUSES for fact in dataset.facts)
    return {
        "received": received,
        "completed": completed,
        "active": active,
        "completion": round(completed / received * 100, 2) if received else 0.0,
    }


def _bottleneck_rows(
    dataset: StatisticsDataset, now: datetime
) -> list[BottleneckMeasure]:
    grouped: defaultdict[RequestStatus, list[StatisticsStageInterval]] = defaultdict(
        list
    )
    for interval in dataset.intervals:
        grouped[interval.status].append(interval)
    facts = {fact.request_id: fact for fact in dataset.facts}
    rows: list[BottleneckMeasure] = []
    for status, intervals in sorted(grouped.items(), key=lambda item: item[0].value):
        if status in TERMINAL_STATUSES:
            continue
        suppressed = len(intervals) < MIN_COHORT
        seconds = sorted(_interval_seconds(item, now) for item in intervals)
        active = [item for item in intervals if item.ended_at is None]
        overdue = sum(
            facts[item.request_id].required_by < now.date()
            for item in active
            if item.request_id in facts
        )
        rows.append(
            BottleneckMeasure(
                key=status.value,
                label=STATUS_LABELS[status],
                active_count=None if suppressed else len(active),
                median_age_hours=None
                if suppressed
                else round(float(median(seconds)) / 3600, 2),
                p90_age_hours=None
                if suppressed
                else round(seconds[max(0, ceil(len(seconds) * 0.9) - 1)] / 3600, 2),
                overdue_count=None if suppressed else overdue,
                suppressed=suppressed,
            )
        )
    return rows


def _interval_seconds(interval: StatisticsStageInterval, now: datetime) -> int:
    if interval.duration_seconds is not None:
        return interval.duration_seconds
    started = interval.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return max(0, round((now - started).total_seconds()))
