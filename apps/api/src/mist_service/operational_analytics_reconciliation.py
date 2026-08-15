"""Bounded repair replay for append-only operational analytics facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.action_notification_models import (
    NotificationEvent,
    NotificationRecipient,
)
from mist_service.board_models import IterationStatus, TeamIteration
from mist_service.calendar_models import CalendarCapacitySnapshot
from mist_service.models import ServiceRequest
from mist_service.operational_analytics_projection import (
    REQUEST_FACT_TYPES,
    project_capacity_snapshot_facts,
    project_closed_iteration_facts,
    project_notification_response_fact,
    project_notification_sent_fact,
    project_product_access_fact,
    project_request_operational_event,
)
from mist_service.product_models import ProductAccessEvent
from mist_service.product_types import AccessOutcome
from mist_service.request_event_models import RequestEvent

MAX_REPLAY_DAYS = 366
MAX_REPLAY_SOURCES = 5_000


@dataclass(frozen=True, slots=True)
class OperationalAnalyticsReplayReport:
    scanned_sources: int
    inserted_facts: int


async def reconcile_operational_analytics(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    source_limit: int = 1_000,
) -> OperationalAnalyticsReplayReport:
    """Replay a bounded UTC window without deleting or rewriting existing facts."""

    start, end = _window(start, end, source_limit)
    request_events = list(
        (
            await session.execute(
                select(RequestEvent, ServiceRequest)
                .join(ServiceRequest, ServiceRequest.id == RequestEvent.request_id)
                .where(
                    func.upper(RequestEvent.type).in_(REQUEST_FACT_TYPES),
                    RequestEvent.created_at >= start,
                    RequestEvent.created_at < end,
                )
                .order_by(RequestEvent.created_at, RequestEvent.id)
                .limit(source_limit + 1)
            )
        ).all()
    )
    access_events = list(
        await session.scalars(
            select(ProductAccessEvent)
            .where(
                ProductAccessEvent.outcome == AccessOutcome.ALLOWED,
                ProductAccessEvent.request_id.is_not(None),
                ProductAccessEvent.created_at >= start,
                ProductAccessEvent.created_at < end,
            )
            .order_by(ProductAccessEvent.created_at, ProductAccessEvent.id)
            .limit(source_limit + 1)
        )
    )
    notifications = list(
        await session.scalars(
            select(NotificationEvent)
            .where(
                NotificationEvent.occurred_at >= start,
                NotificationEvent.occurred_at < end,
            )
            .order_by(NotificationEvent.occurred_at, NotificationEvent.id)
            .limit(source_limit + 1)
        )
    )
    iterations = list(
        await session.scalars(
            select(TeamIteration)
            .where(
                TeamIteration.status == IterationStatus.CLOSED,
                TeamIteration.updated_at >= start,
                TeamIteration.updated_at < end,
            )
            .order_by(TeamIteration.updated_at, TeamIteration.id)
            .limit(source_limit + 1)
        )
    )
    snapshots = list(
        await session.scalars(
            select(CalendarCapacitySnapshot)
            .where(
                CalendarCapacitySnapshot.created_at >= start,
                CalendarCapacitySnapshot.created_at < end,
            )
            .order_by(
                CalendarCapacitySnapshot.created_at,
                CalendarCapacitySnapshot.id,
            )
            .limit(source_limit + 1)
        )
    )
    sources = sum(
        len(items)
        for items in (
            request_events,
            access_events,
            notifications,
            iterations,
            snapshots,
        )
    )
    if sources > source_limit:
        raise ValueError("Reduce the operational analytics replay window.")
    inserted = 0
    for event, request in request_events:
        inserted += await project_request_operational_event(session, event, request)
    for event in access_events:
        inserted += await project_product_access_fact(session, event)
    for event in notifications:
        unit_id, response_at = await _notification_state(session, event)
        inserted += await project_notification_sent_fact(
            session, event, unit_id=unit_id
        )
        if response_at is not None:
            inserted += await project_notification_response_fact(
                session,
                event,
                response_at,
                unit_id=unit_id,
            )
    for iteration in iterations:
        inserted += await project_closed_iteration_facts(session, iteration)
    for snapshot in snapshots:
        inserted += await project_capacity_snapshot_facts(session, snapshot)
    return OperationalAnalyticsReplayReport(sources, inserted)


async def _notification_state(
    session: AsyncSession, event: NotificationEvent
) -> tuple[UUID | None, datetime | None]:
    rows = (
        await session.execute(
            select(
                NotificationRecipient.organisation_unit_id,
                NotificationRecipient.read_at,
                NotificationRecipient.action_completed_at,
            ).where(NotificationRecipient.notification_event_id == event.id)
        )
    ).all()
    unit_id = next((unit for unit, _read, _complete in rows if unit is not None), None)
    responses = [
        value
        for _unit, read_at, completed_at in rows
        for value in (read_at, completed_at)
        if value is not None
    ]
    return unit_id, min(responses) if responses else None


def _window(
    start: datetime, end: datetime, source_limit: int
) -> tuple[datetime, datetime]:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Operational analytics replay dates must include a time zone.")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    if end <= start or end - start > timedelta(days=MAX_REPLAY_DAYS):
        raise ValueError("Operational analytics replay is limited to 366 days.")
    if not 1 <= source_limit <= MAX_REPLAY_SOURCES:
        raise ValueError("Operational analytics replay source limit is invalid.")
    return start, end
