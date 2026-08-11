"""Tracked-request projection using immutable route policy when available."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.models import ServiceRequest
from istari_service.organisation_models import OrganisationUnit, RequestRouteSelection
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
    TrackedRouteUnit,
)
from istari_service.schemas.requests import Sensitivity


async def tracked_requests(
    session: AsyncSession,
    membership: ColumnElement[bool],
    *,
    limit: int,
    cursor: str | None,
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
) -> TrackedRequestDetail | None:
    request = await session.scalar(
        select(ServiceRequest)
        .options(selectinload(ServiceRequest.requester))
        .where(ServiceRequest.id == request_id, membership)
    )
    if request is None:
        return None
    route = (await _tracked_routes(session, {request.id}))[request.id]
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
    )


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
