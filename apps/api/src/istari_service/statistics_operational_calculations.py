"""Cohort-safe calculations for content-free operational fact families."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from math import ceil
from statistics import median
from zoneinfo import ZoneInfo

from istari_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from istari_service.repositories.statistics import StatisticsDataset
from istari_service.schemas.statistics_evolution import (
    CapacityMeasure,
    DemandCapacityProjection,
    IterationMeasure,
    NotificationMeasure,
    ProjectionPeriod,
    ReleaseMeasure,
)

MIN_COHORT = 5
RELEASE_TYPES = {
    OperationalFactType.DISSEMINATION_RELEASED: "Released",
    OperationalFactType.DISSEMINATION_DOWNLOADED: "Managed downloads",
    OperationalFactType.DISSEMINATION_LINK_OPENED: "External links opened",
    OperationalFactType.DISSEMINATION_REPLACED: "Replacements",
    OperationalFactType.DISSEMINATION_WITHDRAWN: "Withdrawals",
}


def release_rows(facts: tuple[OperationalAnalyticsFact, ...]) -> list[ReleaseMeasure]:
    grouped = _group_by_type(facts)
    output: list[ReleaseMeasure] = []
    for fact_type, label in RELEASE_TYPES.items():
        rows = grouped[fact_type]
        if not rows:
            continue
        count = sum(item.count_value for item in rows)
        suppressed = count < MIN_COHORT
        durations = [item.duration_seconds for item in rows if item.duration_seconds]
        output.append(
            ReleaseMeasure(
                key=fact_type.value.lower(),
                label=label,
                count=None if suppressed else count,
                median_hours=(
                    None
                    if suppressed or len(durations) < MIN_COHORT
                    else round(float(median(durations)) / 3600, 2)
                ),
                suppressed=suppressed,
            )
        )
    return output


def notification_rows(
    facts: tuple[OperationalAnalyticsFact, ...],
) -> list[NotificationMeasure]:
    sent = [
        item for item in facts if item.type is OperationalFactType.NOTIFICATION_SENT
    ]
    if not sent:
        return []
    responses = [
        item
        for item in facts
        if item.type is OperationalFactType.NOTIFICATION_RESPONDED
    ]
    legacy_responses = [item for item in sent if item.duration_seconds is not None]
    count = sum(item.count_value for item in sent)
    suppressed = count < MIN_COHORT
    durations = [
        item.duration_seconds
        for item in (*responses, *legacy_responses)
        if item.duration_seconds is not None
    ]
    resolved = sum(item.count_value for item in (*responses, *legacy_responses))
    unresolved = max(0, count - resolved)
    return [
        NotificationMeasure(
            key="notification_sent",
            label="Notifications sent",
            count=None if suppressed else count,
            median_response_hours=(
                None
                if suppressed or len(durations) < MIN_COHORT
                else round(float(median(durations)) / 3600, 2)
            ),
            unresolved_count=None if suppressed else unresolved,
            suppressed=suppressed,
        )
    ]


def iteration_rows(
    facts: tuple[OperationalAnalyticsFact, ...],
) -> list[IterationMeasure]:
    grouped = _group_by_type(facts)
    committed = sum(
        item.count_value for item in grouped[OperationalFactType.ITERATION_COMMITTED]
    )
    completed = sum(
        item.count_value for item in grouped[OperationalFactType.ITERATION_COMPLETED]
    )
    if not committed and not completed:
        return []
    suppressed = committed < MIN_COHORT
    return [
        IterationMeasure(
            key="iteration_completion",
            label="Iteration commitments completed",
            committed_count=None if suppressed else committed,
            completed_count=None if suppressed else completed,
            completion_percentage=(
                None
                if suppressed
                else round(min(completed, committed) / committed * 100, 2)
            ),
            suppressed=suppressed,
        )
    ]


def capacity_rows(
    facts: tuple[OperationalAnalyticsFact, ...], time_zone: ZoneInfo
) -> list[CapacityMeasure]:
    grouped: defaultdict[date, list[OperationalAnalyticsFact]] = defaultdict(list)
    capacity_types = {
        OperationalFactType.CAPACITY_AVAILABLE,
        OperationalFactType.CAPACITY_RESERVED,
        OperationalFactType.PLANNING_ACTIVE_WORK,
        OperationalFactType.PLANNING_DEMAND,
    }
    for item in facts:
        if item.type in capacity_types:
            grouped[_local_date(item.occurred_at, time_zone)].append(item)
    output: list[CapacityMeasure] = []
    for day, rows in sorted(grouped.items()):
        if max(item.count_value for item in rows) < MIN_COHORT:
            continue
        values: defaultdict[OperationalFactType, int] = defaultdict(int)
        for item in rows:
            values[item.type] += item.measure_minutes or 0
        output.append(
            CapacityMeasure(
                date=day,
                available_minutes=values[OperationalFactType.CAPACITY_AVAILABLE],
                reserved_minutes=values[OperationalFactType.CAPACITY_RESERVED],
                active_work_minutes=values[OperationalFactType.PLANNING_ACTIVE_WORK],
                projected_demand_minutes=values[OperationalFactType.PLANNING_DEMAND],
                estimate=True,
            )
        )
    return output


def demand_projection(
    dataset: StatisticsDataset,
    capacity: list[CapacityMeasure],
    from_date: date,
    to_date: date,
) -> DemandCapacityProjection:
    selected_days = (to_date - from_date).days + 1
    if len(dataset.facts) < MIN_COHORT or not capacity:
        periods: list[ProjectionPeriod] = []
    else:
        daily_demand = ceil(len(dataset.facts) / selected_days)
        capacity_count = round(
            sum(item.available_minutes for item in capacity) / len(capacity) / 450
        )
        periods = [
            ProjectionPeriod(
                date=to_date + timedelta(days=offset),
                demand_count=daily_demand,
                capacity_count=max(0, capacity_count),
            )
            for offset in range(1, 15)
        ]
    return DemandCapacityProjection(
        label="Deterministic 14-day estimate from selected aggregate facts.",
        periods=periods,
    )


def _group_by_type(
    facts: tuple[OperationalAnalyticsFact, ...],
) -> defaultdict[OperationalFactType, list[OperationalAnalyticsFact]]:
    output: defaultdict[OperationalFactType, list[OperationalAnalyticsFact]] = (
        defaultdict(list)
    )
    for item in facts:
        output[item.type].append(item)
    return output


def _local_date(value: datetime, time_zone: ZoneInfo) -> date:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(time_zone).date()
