"""Tracked-request projection using immutable route policy when available."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.models import RequestEvent, RequestStatus, ServiceRequest
from istari_service.organisation_models import OrganisationUnit, RequestRouteSelection
from istari_service.product_models import ProductDissemination, ProductPackage
from istari_service.product_types import PackageStatus
from istari_service.repositories.configuration_policies import (
    load_request_configuration_policies,
)
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.schemas.organisation import (
    TrackedRequest,
    TrackedRequestDetail,
    TrackedRequestEvent,
    TrackedRouteUnit,
)
from istari_service.schemas.requests import Sensitivity


async def tracked_requests(
    session: AsyncSession,
    membership: ColumnElement[bool],
    *,
    limit: int,
    cursor: str | None,
    search: str | None = None,
    statuses: tuple[RequestStatus, ...] = (),
    current_owner: str | None = None,
    route_unit_id: UUID | None = None,
    minimum_age_days: int | None = None,
) -> tuple[list[TrackedRequest], str | None]:
    statement = select(
        ServiceRequest.id,
        ServiceRequest.reference,
        ServiceRequest.title,
        ServiceRequest.status,
        ServiceRequest.current_owner,
        ServiceRequest.required_by,
        ServiceRequest.created_at,
        ServiceRequest.updated_at,
        ServiceRequest.awaiting_team_staffing,
    ).where(membership)
    if search:
        term = f"%{search.casefold()}%"
        statement = statement.where(
            or_(
                func.lower(ServiceRequest.reference).like(term),
                func.lower(ServiceRequest.title).like(term),
            )
        )
    if statuses:
        statement = statement.where(ServiceRequest.status.in_(statuses))
    if current_owner:
        statement = statement.where(
            func.lower(ServiceRequest.current_owner).like(
                f"%{current_owner.casefold()}%"
            )
        )
    if route_unit_id:
        statement = statement.where(
            exists_route_selection(route_unit_id)
        )
    if minimum_age_days is not None:
        statement = statement.where(
            ServiceRequest.created_at
            <= datetime.now(UTC) - timedelta(days=minimum_age_days)
        )
    if cursor is not None:
        changed_at, request_id = decode_cursor(
            cursor, message="The tracking filters are invalid."
        )
        statement = statement.where(
            or_(
                ServiceRequest.updated_at < changed_at,
                and_(
                    ServiceRequest.updated_at == changed_at,
                    ServiceRequest.id < request_id,
                ),
            )
        )
    request_rows = (
        await session.execute(
            statement.order_by(
                ServiceRequest.updated_at.desc(), ServiceRequest.id.desc()
            ).limit(limit + 1)
        )
    ).all()
    has_more = len(request_rows) > limit
    request_rows = request_rows[:limit]
    visible_ids = {row.id for row in request_rows}
    if not visible_ids:
        return [], None
    routes = await _tracked_routes(session, visible_ids)
    acceptances = await _customer_acceptances(session, visible_ids)
    items = [
        TrackedRequest(
            id=row.id,
            reference=row.reference,
            title=row.title,
            status=row.status,
            current_owner=row.current_owner,
            required_by=row.required_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
            route=routes[row.id],
            awaiting_team_staffing=row.awaiting_team_staffing,
            age_days=_age_days(row.created_at),
            customer_acceptance_required=row.id in acceptances,
            customer_accepted_at=acceptances.get(row.id),
        )
        for row in request_rows
    ]
    next_cursor = (
        encode_cursor(request_rows[-1].updated_at, request_rows[-1].id)
        if has_more and request_rows
        else None
    )
    return items, next_cursor


async def tracked_request_detail(
    session: AsyncSession,
    membership: ColumnElement[bool],
    request_id: UUID,
    *,
    event_limit: int = 50,
    event_cursor: str | None = None,
) -> TrackedRequestDetail | None:
    request = await session.scalar(
        select(ServiceRequest)
        .options(selectinload(ServiceRequest.requester))
        .where(ServiceRequest.id == request_id, membership)
    )
    if request is None:
        return None
    route = (await _tracked_routes(session, {request.id}))[request.id]
    acceptances = await _customer_acceptances(session, {request.id})
    event_statement = (
        select(RequestEvent)
        .options(selectinload(RequestEvent.actor))
        .where(RequestEvent.request_id == request.id)
    )
    if event_cursor is not None:
        changed_at, event_id = decode_cursor(
            event_cursor, message="The tracking history filters are invalid."
        )
        event_statement = event_statement.where(
            or_(
                RequestEvent.created_at < changed_at,
                and_(
                    RequestEvent.created_at == changed_at,
                    RequestEvent.id < event_id,
                ),
            )
        )
    event_rows = list(
        await session.scalars(
            event_statement.order_by(
                RequestEvent.created_at.desc(), RequestEvent.id.desc()
            ).limit(event_limit + 1)
        )
    )
    has_more_events = len(event_rows) > event_limit
    event_page = event_rows[:event_limit]
    return TrackedRequestDetail(
        id=request.id,
        reference=request.reference,
        title=request.title,
        status=request.status,
        current_owner=request.current_owner,
        required_by=request.required_by,
        created_at=request.created_at,
        updated_at=request.updated_at,
        route=route,
        awaiting_team_staffing=request.awaiting_team_staffing,
        age_days=_age_days(request.created_at),
        customer_acceptance_required=request.id in acceptances,
        customer_accepted_at=acceptances.get(request.id),
        requester_display_name=request.requester.display_name,
        description=request.description,
        question_to_answer=request.question_to_answer,
        desired_outcome=request.desired_outcome,
        background_context=request.background_context,
        subject_area_or_location=request.subject_area_or_location,
        coverage_start=request.coverage_start,
        coverage_end=request.coverage_end,
        customer_urgency=request.customer_urgency,
        supported_activity_or_decision=request.supported_activity_or_decision,
        required_by_reason=request.required_by_reason,
        preferred_deliverable_type=request.preferred_deliverable_type,
        success_criteria=request.success_criteria,
        constraints_or_caveats=request.constraints_or_caveats,
        supporting_information=request.supporting_information,
        sensitivity=Sensitivity(request.sensitivity),
        handling_instructions=request.handling_instructions,
        events=[
            TrackedRequestEvent(
                id=event.id,
                type=event.type,
                message=event.message,
                actor_display_name=(
                    event.actor.display_name if event.actor else None
                ),
                prior_status=event.prior_status,
                next_status=event.next_status,
                created_at=event.created_at,
            )
            for event in reversed(event_page)
        ],
        events_next_cursor=(
            encode_cursor(event_page[-1].created_at, event_page[-1].id)
            if has_more_events and event_page
            else None
        ),
    )


def exists_route_selection(unit_id: UUID) -> ColumnElement[bool]:
    return select(RequestRouteSelection.id).where(
        RequestRouteSelection.request_id == ServiceRequest.id,
        RequestRouteSelection.unit_id == unit_id,
    ).exists()


def _age_days(created_at: datetime) -> int:
    aware = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - aware).days, 0)


async def _customer_acceptances(
    session: AsyncSession,
    request_ids: set[UUID],
) -> dict[UUID, datetime | None]:
    rows = (
        await session.execute(
            select(ProductPackage.request_id, ProductDissemination.accepted_at)
            .join(
                ProductDissemination,
                ProductDissemination.package_id == ProductPackage.id,
            )
            .where(
                ProductPackage.request_id.in_(request_ids),
                ProductPackage.status == PackageStatus.DISSEMINATED,
                ProductDissemination.withdrawn_at.is_(None),
                ProductDissemination.package_checksum
                == ProductPackage.package_checksum,
            )
        )
    ).all()
    return dict(rows)


async def _tracked_routes(
    session: AsyncSession,
    request_ids: set[UUID],
) -> defaultdict[UUID, list[TrackedRouteUnit]]:
    route_rows = (
        await session.execute(
            select(
                RequestRouteSelection.request_id,
                RequestRouteSelection.position,
                RequestRouteSelection.unit_id,
            )
            .where(RequestRouteSelection.request_id.in_(request_ids))
            .order_by(RequestRouteSelection.request_id, RequestRouteSelection.position)
        )
    ).all()
    policies = await load_request_configuration_policies(session, request_ids)
    legacy_unit_ids = {
        row.unit_id for row in route_rows if row.request_id not in policies
    }
    legacy_units = (
        {
            unit.id: unit
            for unit in await session.scalars(
                select(OrganisationUnit).where(OrganisationUnit.id.in_(legacy_unit_ids))
            )
        }
        if legacy_unit_ids
        else {}
    )
    routes: defaultdict[UUID, list[TrackedRouteUnit]] = defaultdict(list)
    for row in route_rows:
        policy = policies.get(row.request_id)
        if policy is not None:
            unit = policy.units.get(row.unit_id)
            if unit is None:
                raise RuntimeError("the pinned request route is invalid")
            name, kind = unit.name, unit.kind
        else:
            legacy = legacy_units.get(row.unit_id)
            if legacy is None:
                raise RuntimeError("the legacy request route is invalid")
            name, kind = legacy.name, legacy.kind
        routes[row.request_id].append(
            TrackedRouteUnit(id=row.unit_id, name=name, kind=kind)
        )
    return routes
