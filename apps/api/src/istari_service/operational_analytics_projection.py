"""Project authoritative domain activity into append-only operational facts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import NotificationEvent
from istari_service.analytics_evolution_models import OperationalFactType
from istari_service.board_models import (
    IterationStatus,
    TeamIteration,
    WorkPackage,
    WorkPackageStatus,
)
from istari_service.calendar_models import CalendarCapacitySnapshot
from istari_service.models import RequestEvent, ServiceRequest
from istari_service.operational_analytics_facts import (
    OperationalFactInput,
    anonymous_source_key,
    append_operational_fact,
    elapsed_seconds,
    request_operational_scope,
    unit_operational_scope,
)
from istari_service.planning_capacity import calculate_planning_capacity
from istari_service.product_models import ProductAccessEvent, ProductPackage
from istari_service.product_types import AccessKind, AccessOutcome
from istari_service.schemas.calendar import CapacityDay

REQUEST_FACT_TYPES = {
    # QC dissemination is the authoritative managed-release boundary. Workflow
    # completion can occur in the same journey and must not count as delivery.
    "PRODUCT_DISSEMINATED": OperationalFactType.DISSEMINATION_RELEASED,
    "PRODUCT_REPLACED": OperationalFactType.DISSEMINATION_REPLACED,
    "PRODUCT_WITHDRAWN": OperationalFactType.DISSEMINATION_WITHDRAWN,
}
ACTIVE_WORK = {WorkPackageStatus.IN_PROGRESS, WorkPackageStatus.BLOCKED}
OPEN_DEMAND = {
    WorkPackageStatus.BACKLOG,
    WorkPackageStatus.READY,
    WorkPackageStatus.IN_PROGRESS,
    WorkPackageStatus.BLOCKED,
}


async def project_request_operational_event(
    session: AsyncSession,
    event: RequestEvent,
    request: ServiceRequest,
) -> int:
    fact_type = REQUEST_FACT_TYPES.get(event.type.upper())
    if fact_type is None:
        return 0
    scope = await request_operational_scope(session, request.id)
    if scope is None:
        return 0
    duration = (
        elapsed_seconds(request.created_at, event.created_at)
        if fact_type is OperationalFactType.DISSEMINATION_RELEASED
        else None
    )
    inserted = await append_operational_fact(
        session,
        OperationalFactInput(
            source_key=anonymous_source_key("request-event", event.id, fact_type.value),
            type=fact_type,
            scope=scope,
            occurred_at=event.created_at,
            duration_seconds=duration,
        ),
    )
    return int(inserted)


async def project_product_access_fact(
    session: AsyncSession, event: ProductAccessEvent
) -> int:
    if event.outcome is not AccessOutcome.ALLOWED or event.request_id is None:
        return 0
    fact_type = {
        AccessKind.DOWNLOAD: OperationalFactType.DISSEMINATION_DOWNLOADED,
        AccessKind.REDIRECT: OperationalFactType.DISSEMINATION_LINK_OPENED,
    }[event.kind]
    scope = await request_operational_scope(session, event.request_id)
    if scope is None:
        return 0
    released_at = None
    if event.package_id is not None:
        released_at = await session.scalar(
            select(ProductPackage.disseminated_at).where(
                ProductPackage.id == event.package_id
            )
        )
    inserted = await append_operational_fact(
        session,
        OperationalFactInput(
            source_key=anonymous_source_key(
                "product-access", event.id, fact_type.value
            ),
            type=fact_type,
            scope=scope,
            occurred_at=event.created_at,
            duration_seconds=(
                elapsed_seconds(released_at, event.created_at) if released_at else None
            ),
        ),
    )
    return int(inserted)


async def project_notification_sent_fact(
    session: AsyncSession,
    event: NotificationEvent,
    *,
    unit_id: UUID | None = None,
) -> int:
    scope = (
        await request_operational_scope(session, event.request_id)
        if event.request_id is not None
        else await unit_operational_scope(session, unit_id)
        if unit_id is not None
        else None
    )
    if scope is None:
        return 0
    inserted = await append_operational_fact(
        session,
        OperationalFactInput(
            source_key=anonymous_source_key(
                "notification", event.id, OperationalFactType.NOTIFICATION_SENT.value
            ),
            type=OperationalFactType.NOTIFICATION_SENT,
            scope=scope,
            occurred_at=event.occurred_at,
        ),
    )
    return int(inserted)


async def project_notification_response_fact(
    session: AsyncSession,
    event: NotificationEvent,
    response_at: datetime,
    *,
    unit_id: UUID | None = None,
) -> int:
    scope = (
        await request_operational_scope(session, event.request_id)
        if event.request_id is not None
        else await unit_operational_scope(session, unit_id)
        if unit_id is not None
        else None
    )
    if scope is None:
        return 0
    inserted = await append_operational_fact(
        session,
        OperationalFactInput(
            source_key=anonymous_source_key(
                "notification",
                event.id,
                OperationalFactType.NOTIFICATION_RESPONDED.value,
            ),
            type=OperationalFactType.NOTIFICATION_RESPONDED,
            scope=scope,
            occurred_at=event.occurred_at,
            duration_seconds=elapsed_seconds(event.occurred_at, response_at),
        ),
    )
    return int(inserted)


async def project_closed_iteration_facts(
    session: AsyncSession,
    iteration: TeamIteration,
    *,
    occurred_at: datetime | None = None,
) -> int:
    if iteration.status is not IterationStatus.CLOSED:
        return 0
    scope = await unit_operational_scope(session, iteration.team_id)
    if scope is None:
        return 0
    rows = (
        await session.execute(
            select(WorkPackage.status, func.count(WorkPackage.id))
            .where(WorkPackage.iteration_id == iteration.id)
            .group_by(WorkPackage.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    committed = sum(
        count
        for status, count in counts.items()
        if status is not WorkPackageStatus.CANCELLED
    )
    completed = counts.get(WorkPackageStatus.DONE, 0)
    when = occurred_at or iteration.updated_at
    inserted = 0
    for fact_type, count in (
        (OperationalFactType.ITERATION_COMMITTED, committed),
        (OperationalFactType.ITERATION_COMPLETED, completed),
    ):
        inserted += int(
            await append_operational_fact(
                session,
                OperationalFactInput(
                    source_key=anonymous_source_key(
                        "iteration", iteration.id, fact_type.value
                    ),
                    type=fact_type,
                    scope=scope,
                    occurred_at=when,
                    count_value=count,
                ),
            )
        )
    return inserted


async def project_capacity_snapshot_facts(
    session: AsyncSession,
    snapshot: CalendarCapacitySnapshot,
    *,
    occurred_at: datetime | None = None,
) -> int:
    scope = await unit_operational_scope(session, snapshot.team_id)
    if scope is None:
        return 0
    days = [CapacityDay.model_validate(item) for item in snapshot.days]
    member_count = max((item.member_count for item in days), default=0)
    projection = await calculate_planning_capacity(
        session,
        team_id=snapshot.team_id,
        date_from=snapshot.date_from,
        date_to=snapshot.date_to,
        time_zone_name=snapshot.time_zone,
    )
    package_rows = (
        await session.execute(
            select(WorkPackage.status, WorkPackage.remaining_effort_minutes).where(
                WorkPackage.team_id == snapshot.team_id
            )
        )
    ).all()
    measures = {
        OperationalFactType.CAPACITY_AVAILABLE: sum(
            item.available_minutes for item in days
        ),
        OperationalFactType.CAPACITY_RESERVED: projection.reserved_minutes,
        OperationalFactType.PLANNING_ACTIVE_WORK: sum(
            minutes for status, minutes in package_rows if status in ACTIVE_WORK
        ),
        OperationalFactType.PLANNING_DEMAND: sum(
            minutes for status, minutes in package_rows if status in OPEN_DEMAND
        ),
    }
    when = occurred_at or snapshot.created_at
    inserted = 0
    for fact_type, minutes in measures.items():
        inserted += int(
            await append_operational_fact(
                session,
                OperationalFactInput(
                    source_key=anonymous_source_key(
                        "capacity-snapshot", snapshot.id, fact_type.value
                    ),
                    type=fact_type,
                    scope=scope,
                    occurred_at=when,
                    count_value=member_count,
                    measure_minutes=minutes,
                ),
            )
        )
    return inserted
