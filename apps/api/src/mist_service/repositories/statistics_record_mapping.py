"""Map persistence projections onto framework-free statistics records."""

from __future__ import annotations

from mist_service.analytics_evolution_models import OperationalAnalyticsFact
from mist_service.analytics_models import (
    AnalyticsProjectionState,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from mist_service.organisation_models import OrganisationUnit
from mist_service.statistics_records import (
    OperationalStatisticsFact,
    StatisticsChild,
    StatisticsFact,
    StatisticsFreshness,
    StatisticsStageInterval,
)


def statistics_fact(row: RequestAnalyticsFact) -> StatisticsFact:
    return StatisticsFact(
        request_id=row.request_id,
        command_unit_id=row.command_unit_id,
        ops_unit_id=row.ops_unit_id,
        team_unit_id=row.team_unit_id,
        received_at=row.received_at,
        required_by=row.required_by,
        current_status=row.current_status,
        completed_at=row.completed_at,
        released_at=row.released_at,
        clarification_count=row.clarification_count,
        clarification_response_seconds=row.clarification_response_seconds,
        rework_count=row.rework_count,
        feedback_received=row.feedback_received,
        feedback_rating=row.feedback_rating,
    )


def statistics_interval(row: RequestStageInterval) -> StatisticsStageInterval:
    return StatisticsStageInterval(
        request_id=row.request_id,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_seconds=row.duration_seconds,
    )


def statistics_child(row: OrganisationUnit) -> StatisticsChild:
    return StatisticsChild(id=row.id, name=row.name, kind=row.kind)


def statistics_freshness(
    row: AnalyticsProjectionState | None,
) -> StatisticsFreshness | None:
    if row is None:
        return None
    return StatisticsFreshness(
        health=row.health,
        last_projected_at=row.last_projected_at,
        source_event_count=row.source_event_count,
        projected_request_count=row.projected_request_count,
    )


def operational_statistics_fact(
    row: OperationalAnalyticsFact,
) -> OperationalStatisticsFact:
    return OperationalStatisticsFact(
        type=row.type,
        occurred_at=row.occurred_at,
        count_value=row.count_value,
        duration_seconds=row.duration_seconds,
        measure_minutes=row.measure_minutes,
    )
