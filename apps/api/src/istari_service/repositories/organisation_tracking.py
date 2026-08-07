"""Tracked-request projection using immutable route policy when available."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_request_policy import (
    load_request_configuration_policy,
)
from istari_service.models import ServiceRequest
from istari_service.organisation_models import OrganisationUnit, RequestRouteSelection
from istari_service.schemas.organisation import TrackedRequest, TrackedRouteUnit


async def tracked_requests(
    session: AsyncSession,
    membership: ColumnElement[bool],
) -> list[TrackedRequest]:
    request_rows = (
        await session.execute(
            select(
                ServiceRequest.id,
                ServiceRequest.reference,
                ServiceRequest.status,
                ServiceRequest.current_owner,
                ServiceRequest.required_by,
                ServiceRequest.updated_at,
                ServiceRequest.awaiting_team_staffing,
            )
            .where(membership)
            .order_by(ServiceRequest.updated_at.desc(), ServiceRequest.id)
        )
    ).all()
    visible_ids = {row.id for row in request_rows}
    if not visible_ids:
        return []
    route_rows = (
        await session.execute(
            select(
                RequestRouteSelection.request_id,
                RequestRouteSelection.position,
                RequestRouteSelection.unit_id,
            )
            .where(RequestRouteSelection.request_id.in_(visible_ids))
            .order_by(RequestRouteSelection.request_id, RequestRouteSelection.position)
        )
    ).all()
    unit_ids = {row.unit_id for row in route_rows}
    legacy_units = {
        unit.id: unit
        for unit in await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.id.in_(unit_ids))
        )
    }
    policies = {
        request_id: await load_request_configuration_policy(session, request_id)
        for request_id in visible_ids
    }
    routes: dict[UUID, list[TrackedRouteUnit]] = defaultdict(list)
    for row in route_rows:
        policy = policies[row.request_id]
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
    return [
        TrackedRequest(
            id=row.id,
            reference=row.reference,
            status=row.status,
            current_owner=row.current_owner,
            required_by=row.required_by,
            updated_at=row.updated_at,
            route=routes[row.id],
            awaiting_team_staffing=row.awaiting_team_staffing,
        )
        for row in request_rows
    ]
