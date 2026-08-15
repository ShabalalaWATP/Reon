"""Reusable live route-membership predicates."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.models import ServiceRequest, UserRole
from mist_service.organisation_models import RequestRouteSelection
from mist_service.team_models import TeamMembership

ROUTE_POSITION_BY_ROLE = {
    UserRole.INTAKE_TRIAGE: 0,
    UserRole.SERVICE_COORDINATION: 1,
    UserRole.OPERATIONS_ALLOCATION: 2,
    UserRole.DELIVERY_TEAM_LEAD: 3,
    UserRole.DELIVERY_SPECIALIST: 3,
}


def live_unit_membership_condition(
    user_id: Any,
    unit_id: Any,
    at: datetime,
) -> ColumnElement[bool]:
    """Require a live membership in one exact unit."""

    return exists().where(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == unit_id,
        TeamMembership.effective_from <= at,
        or_(
            TeamMembership.effective_until.is_(None),
            TeamMembership.effective_until > at,
        ),
    )


def live_selected_route_membership_condition(
    actor: Actor,
    request_id: Any,
    at: datetime,
) -> ColumnElement[bool]:
    """Require live membership in the request's exact selected route unit."""

    position = ROUTE_POSITION_BY_ROLE.get(actor.role)
    if position is None:
        return false()
    conditions: list[ColumnElement[bool]] = [
        RequestRouteSelection.request_id == request_id,
        RequestRouteSelection.position == position,
        live_unit_membership_condition(
            actor.id,
            RequestRouteSelection.unit_id,
            at,
        ),
    ]
    if position == 3:
        assigned_team = exists().where(
            ServiceRequest.id == RequestRouteSelection.request_id,
            ServiceRequest.assigned_delivery_team_id == RequestRouteSelection.unit_id,
        )
        conditions.append(assigned_team)
    return exists().where(*conditions)


def route_membership_condition(actor: Actor) -> ColumnElement[bool] | None:
    """Match requests that have travelled through the actor's exact route unit."""

    position = ROUTE_POSITION_BY_ROLE.get(actor.role)
    if position is None:
        return None
    unit_ids = actor.organisation_unit_ids
    if not unit_ids:
        return ServiceRequest.id.is_(None)
    if position == 3:
        stable_membership = exists().where(
            ServiceRequest.assigned_delivery_team_id.in_(unit_ids),
            RequestRouteSelection.request_id == ServiceRequest.id,
            RequestRouteSelection.position == position,
            RequestRouteSelection.unit_id == ServiceRequest.assigned_delivery_team_id,
        )
        routed_membership = exists().where(
            RequestRouteSelection.unit_id.in_(unit_ids),
            RequestRouteSelection.request_id == ServiceRequest.id,
            RequestRouteSelection.position == position,
        )
        return or_(
            and_(
                ServiceRequest.assigned_delivery_team_id.is_not(None),
                stable_membership,
            ),
            and_(
                ServiceRequest.assigned_delivery_team_id.is_(None),
                routed_membership,
            ),
        )
    return exists().where(
        RequestRouteSelection.unit_id.in_(unit_ids),
        RequestRouteSelection.request_id == ServiceRequest.id,
        RequestRouteSelection.position == position,
    )


async def has_route_membership(
    session: AsyncSession,
    actor: Actor,
    request_id: UUID,
    *,
    lock: bool = False,
) -> bool:
    """Check exact route membership, optionally locking the selected route row."""

    position = ROUTE_POSITION_BY_ROLE.get(actor.role)
    if position is None:
        return True
    if not actor.organisation_unit_ids:
        return False
    if position == 3:
        team_id = await session.scalar(
            select(ServiceRequest.assigned_delivery_team_id).where(
                ServiceRequest.id == request_id
            )
        )
        if team_id is not None and team_id in actor.organisation_unit_ids:
            query = select(RequestRouteSelection.id).where(
                RequestRouteSelection.unit_id == team_id,
                RequestRouteSelection.request_id == request_id,
                RequestRouteSelection.position == position,
            )
            if lock:
                query = query.with_for_update()
            return await session.scalar(query) is not None
    query = select(RequestRouteSelection.id).where(
        RequestRouteSelection.request_id == request_id,
        RequestRouteSelection.position == position,
        RequestRouteSelection.unit_id.in_(actor.organisation_unit_ids),
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query) is not None
