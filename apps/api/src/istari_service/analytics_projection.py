"""Idempotent content-free facts derived from authoritative request history."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from istari_service.clarification_models import (
    ClarificationStatus,
    ClarificationThread,
)
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
)
from istari_service.organisation_models import RequestRouteSelection

PROJECTION_NAME = "request-operations"
PROJECTION_VERSION = 1
ROOT_STAGES = {
    RequestStatus.ROUTING_PENDING,
    RequestStatus.TRIAGE_REVIEW,
    RequestStatus.INFORMATION_REQUIRED,
}
COMMAND_STAGES = {RequestStatus.COORDINATION_REVIEW, RequestStatus.ON_HOLD}
OPS_STAGES = {RequestStatus.ALLOCATION_REVIEW}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _stage_unit(status: RequestStatus, route: dict[int, UUID]) -> UUID:
    if status in ROOT_STAGES:
        return route[0]
    if status in COMMAND_STAGES:
        return route.get(1, route[0])
    if status in OPS_STAGES:
        return route.get(2, route.get(1, route[0]))
    return route.get(3, route.get(2, route.get(1, route[0])))


def _apply_route_event(event: RequestEvent, route: dict[int, UUID]) -> None:
    action = str(event.details.get("action", ""))
    position = event.details.get("routePosition")
    unit_value = event.details.get("routeUnitId")
    if isinstance(position, int) and position in {1, 2, 3} and unit_value:
        with suppress(ValueError):
            route[position] = UUID(str(unit_value))
        for child_position in range(position + 1, 4):
            route.pop(child_position, None)
    clear_from = {
        "return_to_triage": 1,
        "return_to_coordination": 2,
        "return_for_reallocation": 3,
    }.get(action)
    if clear_from is not None:
        for child_position in range(clear_from, 4):
            route.pop(child_position, None)


async def project_request_analytics(
    session: AsyncSession,
    request_id: UUID,
    *,
    projected_at: datetime | None = None,
    update_checkpoint: bool = True,
) -> RequestAnalyticsFact:
    """Replace one deterministic projection without reading request content."""

    request = await session.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise LookupError("The request projection source does not exist.")
    route_rows = (
        await session.execute(
            select(
                RequestRouteSelection.position,
                RequestRouteSelection.unit_id,
            ).where(RequestRouteSelection.request_id == request_id)
        )
    ).all()
    route: dict[int, UUID] = {}
    for position, unit_id in route_rows:
        route[position] = unit_id
    if 0 not in route:
        raise RuntimeError("The request has no root routing selection.")
    events = list(
        await session.scalars(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
        )
    )
    now = projected_at or datetime.now(UTC)
    fact = await session.get(RequestAnalyticsFact, request_id)
    is_new = fact is None
    if fact is None:
        fact = RequestAnalyticsFact(request_id=request_id)
    await _populate_fact(session, fact, request, route, events, now)
    if is_new:
        session.add(fact)
    await _replace_stage_intervals(session, request, route[0], events)
    await session.flush()
    if update_checkpoint:
        await _update_checkpoint(session, now)
    return fact


async def rebuild_analytics_projections(
    session: AsyncSession,
    *,
    projected_at: datetime | None = None,
) -> int:
    now = projected_at or datetime.now(UTC)
    state = await _projection_state(session)
    state.health = ProjectionHealth.REBUILDING
    await session.flush()
    request_ids = tuple(await session.scalars(select(ServiceRequest.id)))
    for request_id in request_ids:
        await project_request_analytics(
            session,
            request_id,
            projected_at=now,
            update_checkpoint=False,
        )
    await _update_checkpoint(session, now)
    return len(request_ids)


async def _populate_fact(
    session: AsyncSession,
    fact: RequestAnalyticsFact,
    request: ServiceRequest,
    route: dict[int, UUID],
    events: list[RequestEvent],
    now: datetime,
) -> None:
    transitions = [event for event in events if event.next_status != event.prior_status]
    terminal = {
        event.next_status: _aware(event.created_at)
        for event in transitions
        if event.next_status
        in {
            RequestStatus.COMPLETED,
            RequestStatus.CLOSED_NOT_PROGRESSED,
            RequestStatus.CANCELLED,
        }
    }
    released_at = await session.scalar(
        select(func.max(Deliverable.released_at)).where(
            Deliverable.request_id == request.id,
            Deliverable.status == DeliverableStatus.RELEASED,
        )
    )
    feedback = await session.scalar(
        select(Feedback).where(Feedback.request_id == request.id)
    )
    clarifications = list(
        await session.scalars(
            select(ClarificationThread).where(
                ClarificationThread.request_id == request.id
            )
        )
    )
    response_seconds = sum(
        max(
            0,
            int((_aware(thread.closed_at) - _aware(thread.created_at)).total_seconds()),
        )
        for thread in clarifications
        if thread.status is ClarificationStatus.ANSWERED
        and thread.closed_at is not None
    )
    fact.root_unit_id = route[0]
    fact.command_unit_id = route.get(1)
    fact.ops_unit_id = route.get(2)
    fact.team_unit_id = route.get(3)
    fact.received_at = _aware(request.created_at)
    fact.required_by = request.required_by
    fact.current_status = request.status
    fact.last_transition_at = (
        _aware(transitions[-1].created_at)
        if transitions
        else _aware(request.created_at)
    )
    fact.completed_at = terminal.get(RequestStatus.COMPLETED)
    fact.closed_at = terminal.get(RequestStatus.CLOSED_NOT_PROGRESSED) or terminal.get(
        RequestStatus.CANCELLED
    )
    fact.released_at = _aware(released_at) if released_at else None
    fact.clarification_count = len(clarifications)
    fact.clarification_response_seconds = response_seconds
    fact.rework_count = sum(
        event.next_status is RequestStatus.REWORK_REQUIRED for event in transitions
    )
    fact.feedback_received = feedback is not None
    fact.feedback_rating = feedback.rating if feedback else None
    fact.projection_version = PROJECTION_VERSION
    fact.source_event_count = len(events)
    fact.projected_at = now


async def _replace_stage_intervals(
    session: AsyncSession,
    request: ServiceRequest,
    root_unit_id: UUID,
    events: list[RequestEvent],
) -> None:
    await session.execute(
        delete(RequestStageInterval).where(
            RequestStageInterval.request_id == request.id
        )
    )
    route: dict[int, UUID] = {0: root_unit_id}
    current_status = RequestStatus.ROUTING_PENDING
    current_unit = root_unit_id
    started_at = _aware(request.created_at)
    source_event_id: UUID | None = None
    intervals: list[RequestStageInterval] = []
    for event in events:
        _apply_route_event(event, route)
        if event.next_status is None or event.next_status is current_status:
            continue
        ended_at = max(started_at, _aware(event.created_at))
        intervals.append(
            _interval(
                request.id,
                len(intervals) + 1,
                current_status,
                current_unit,
                started_at,
                ended_at,
                source_event_id,
            )
        )
        current_status = event.next_status
        current_unit = _stage_unit(current_status, route)
        started_at = ended_at
        source_event_id = event.id
    intervals.append(
        _interval(
            request.id,
            len(intervals) + 1,
            current_status,
            current_unit,
            started_at,
            None,
            source_event_id,
        )
    )
    session.add_all(intervals)


def _interval(
    request_id: UUID,
    sequence: int,
    status: RequestStatus,
    unit_id: UUID,
    started_at: datetime,
    ended_at: datetime | None,
    source_event_id: UUID | None,
) -> RequestStageInterval:
    duration = int((ended_at - started_at).total_seconds()) if ended_at else None
    return RequestStageInterval(
        request_id=request_id,
        sequence=sequence,
        status=status,
        unit_id=unit_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration,
        source_event_id=source_event_id,
    )


async def _projection_state(session: AsyncSession) -> AnalyticsProjectionState:
    state = await session.get(AnalyticsProjectionState, PROJECTION_NAME)
    if state is None:
        state = AnalyticsProjectionState(
            name=PROJECTION_NAME,
            projection_version=PROJECTION_VERSION,
            health=ProjectionHealth.REBUILDING,
        )
        session.add(state)
    return state


async def _update_checkpoint(session: AsyncSession, now: datetime) -> None:
    state = await _projection_state(session)
    state.projection_version = PROJECTION_VERSION
    state.health = ProjectionHealth.READY
    state.source_event_count = int(
        await session.scalar(select(func.sum(RequestAnalyticsFact.source_event_count)))
        or 0
    )
    state.projected_request_count = int(
        await session.scalar(select(func.count(RequestAnalyticsFact.request_id))) or 0
    )
    state.last_projected_at = now
