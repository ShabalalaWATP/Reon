"""Pure, reproducible calculations over content-free statistics rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from math import ceil
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo

from mist_service.analytics_models import ProjectionHealth
from mist_service.models import RequestStatus
from mist_service.schemas.statistics import (
    CategoryCount,
    MetricDefinition,
    ProjectionFreshness,
    StageDuration,
    StatisticsDashboard,
    StatisticsRange,
    SummaryMetric,
)
from mist_service.statistics_children import child_comparisons
from mist_service.statistics_records import (
    StatisticsDataset,
    StatisticsFact,
    StatisticsStageInterval,
)
from mist_service.statistics_throughput import (
    local_date,
    throughput_resolution,
    throughput_rows,
)

RATING_COHORT = 5
MetricUnit = Literal["count", "percentage", "rating", "hours"]
TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}
STATUS_LABELS = {
    status: status.value.replace("_", " ").title() for status in RequestStatus
}
STATUS_LABELS.update(
    {
        RequestStatus.CUSTOMER_INFORMATION_REQUIRED: "Awaiting Customer information",
        RequestStatus.CLOSED_NOT_PROGRESSED: "Closed without delivery",
        RequestStatus.READY_FOR_RELEASE: "Ready for release",
    }
)
DEFINITIONS = (
    MetricDefinition(
        key="received",
        label="Received",
        description="Requests received in the selected date range and scope.",
    ),
    MetricDefinition(
        key="active",
        label="Active work",
        description="Selected requests that have not reached a terminal state.",
    ),
    MetricDefinition(
        key="completed",
        label="Completed",
        description="Selected requests successfully released to the Customer.",
    ),
    MetricDefinition(
        key="overdue",
        label="Overdue",
        description="Active requests whose required date is before the as-of date.",
    ),
    MetricDefinition(
        key="average_rating",
        label="Average rating",
        description="Mean Customer rating, suppressed below five responses.",
    ),
)


def build_statistics_dashboard(
    dataset: StatisticsDataset,
    *,
    from_date: date,
    to_date: date,
    time_zone: ZoneInfo,
    as_of_date: date,
) -> StatisticsDashboard:
    facts = dataset.facts
    active = tuple(
        fact for fact in facts if fact.current_status not in TERMINAL_STATUSES
    )
    ratings = [
        fact.feedback_rating for fact in facts if fact.feedback_rating is not None
    ]
    rating_suppressed = len(ratings) < RATING_COHORT
    overdue = sum(fact.required_by < as_of_date for fact in active)
    resolution = throughput_resolution(from_date, to_date)
    summary = _summary_metrics(
        facts,
        active_count=len(active),
        overdue=overdue,
        ratings=ratings,
        rating_suppressed=rating_suppressed,
    )
    freshness = dataset.freshness
    return StatisticsDashboard(
        scope=dataset.scope,
        selected_unit=dataset.selected_unit,
        breadcrumb=list(dataset.breadcrumb),
        range=StatisticsRange(
            from_date=from_date,
            to_date=to_date,
            time_zone=time_zone.key,
            as_of_date=as_of_date,
        ),
        freshness=ProjectionFreshness(
            health=freshness.health if freshness else ProjectionHealth.DEGRADED,
            last_projected_at=freshness.last_projected_at if freshness else None,
            source_event_count=freshness.source_event_count if freshness else 0,
            projected_request_count=(
                freshness.projected_request_count if freshness else 0
            ),
        ),
        definitions=list(DEFINITIONS),
        summary=summary,
        status=_status_rows(facts),
        age=_age_rows(active, as_of_date, time_zone),
        due_risk=_due_rows(active, as_of_date),
        throughput_resolution=resolution,
        throughput=throughput_rows(
            facts,
            from_date,
            to_date,
            time_zone,
            resolution,
        ),
        stage_durations=_stage_rows(dataset.intervals),
        children=child_comparisons(
            dataset.selected_unit.kind,
            facts,
            dataset.children,
            as_of_date,
        ),
    )


def _summary_metrics(
    facts: tuple[StatisticsFact, ...],
    *,
    active_count: int,
    overdue: int,
    ratings: list[int],
    rating_suppressed: bool,
) -> list[SummaryMetric]:
    completed = sum(fact.current_status is RequestStatus.COMPLETED for fact in facts)
    closed = sum(
        fact.current_status
        in {RequestStatus.CLOSED_NOT_PROGRESSED, RequestStatus.CANCELLED}
        for fact in facts
    )
    released = sum(fact.released_at is not None for fact in facts)
    feedback = sum(fact.feedback_received for fact in facts)
    clarification_count = sum(fact.clarification_count for fact in facts)
    rework_count = sum(fact.rework_count for fact in facts)
    response_seconds = sum(fact.clarification_response_seconds for fact in facts)
    average_response = (
        round(response_seconds / clarification_count / 3600, 1)
        if clarification_count
        else 0.0
    )
    average_rating = (
        None if rating_suppressed else round(sum(ratings) / len(ratings), 2)
    )
    values: tuple[tuple[str, str, int | float | None, MetricUnit, bool], ...] = (
        ("received", "Received", len(facts), "count", False),
        (
            "routed",
            "Routed",
            sum(f.command_unit_id is not None for f in facts),
            "count",
            False,
        ),
        ("active", "Active work", active_count, "count", False),
        ("completed", "Completed", completed, "count", False),
        ("closed", "Closed", closed, "count", False),
        ("released", "Products released", released, "count", False),
        ("overdue", "Overdue", overdue, "count", False),
        (
            "clarifications",
            "Clarification requests",
            clarification_count,
            "count",
            False,
        ),
        (
            "clarification_hours",
            "Mean clarification response",
            average_response,
            "hours",
            False,
        ),
        ("rework", "Rework decisions", rework_count, "count", False),
        ("feedback", "Feedback received", feedback, "count", False),
        (
            "average_rating",
            "Average rating",
            average_rating,
            "rating",
            rating_suppressed,
        ),
    )
    return [
        SummaryMetric(
            key=key,
            label=label,
            value=value,
            unit=unit,
            suppressed=suppressed,
        )
        for key, label, value, unit, suppressed in values
    ]


def _status_rows(
    facts: tuple[StatisticsFact, ...],
) -> list[CategoryCount]:
    counts = Counter(fact.current_status for fact in facts)
    return [
        CategoryCount(
            key=status.value, label=STATUS_LABELS[status], count=counts[status]
        )
        for status in RequestStatus
        if counts[status]
    ]


def _age_rows(
    facts: tuple[StatisticsFact, ...],
    as_of_date: date,
    time_zone: ZoneInfo,
) -> list[CategoryCount]:
    counts = [0, 0, 0, 0]
    for fact in facts:
        age = max(0, (as_of_date - local_date(fact.received_at, time_zone)).days)
        index = 0 if age <= 2 else 1 if age <= 7 else 2 if age <= 14 else 3
        counts[index] += 1
    labels = ("0-2 days", "3-7 days", "8-14 days", "15+ days")
    return [
        CategoryCount(key=f"age-{index}", label=label, count=counts[index])
        for index, label in enumerate(labels)
    ]


def _due_rows(
    facts: tuple[StatisticsFact, ...],
    as_of_date: date,
) -> list[CategoryCount]:
    counts = [0, 0, 0]
    for fact in facts:
        if fact.required_by < as_of_date:
            counts[0] += 1
        elif fact.required_by <= as_of_date + timedelta(days=7):
            counts[1] += 1
        else:
            counts[2] += 1
    labels = ("Overdue", "Due within 7 days", "Due later")
    return [
        CategoryCount(key=f"due-{index}", label=label, count=counts[index])
        for index, label in enumerate(labels)
    ]


def _stage_rows(
    intervals: tuple[StatisticsStageInterval, ...],
) -> list[StageDuration]:
    grouped: dict[RequestStatus, list[int]] = defaultdict(list)
    for interval in intervals:
        if interval.duration_seconds is not None:
            grouped[interval.status].append(interval.duration_seconds)
    rows: list[StageDuration] = []
    for status in RequestStatus:
        values = sorted(grouped[status])
        if not values:
            continue
        p90 = values[max(0, ceil(len(values) * 0.9) - 1)]
        rows.append(
            StageDuration(
                key=status.value,
                label=STATUS_LABELS[status],
                completed_intervals=len(values),
                median_hours=round(float(median(values)) / 3600, 2),
                p90_hours=round(p90 / 3600, 2),
            )
        )
    return rows
