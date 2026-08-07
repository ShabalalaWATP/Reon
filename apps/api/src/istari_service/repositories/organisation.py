"""Organisation hierarchy, route validation and metadata-only tracking."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, ServiceRequest, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
    StaffingStatus,
    UserOrganisationMembership,
)
from istari_service.schemas.organisation import (
    OrganisationUnitView,
    TrackedRequest,
    TrackedRouteUnit,
)
from istari_service.schemas.work import (
    AllocateRequest,
    CompletionPayload,
    ProgressRequest,
    SendToAllocation,
)
from istari_service.work_command_types import RoutingSelection

GROUP_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?")
ROUTE_POSITION_BY_ROLE = {
    UserRole.INTAKE_TRIAGE: 0,
    UserRole.SERVICE_COORDINATION: 1,
    UserRole.OPERATIONS_ALLOCATION: 2,
    UserRole.DELIVERY_TEAM_LEAD: 3,
    UserRole.DELIVERY_SPECIALIST: 3,
}


@dataclass(frozen=True, slots=True)
class RoutingSpec:
    parent_position: int
    selected_position: int
    expected_kind: OrganisationKind
    destination_id: UUID


class SqlAlchemyOrganisationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_units(self) -> list[OrganisationUnitView]:
        units = (
            await self._session.scalars(
                select(OrganisationUnit)
                .where(OrganisationUnit.is_configured.is_(True))
                .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            )
        ).all()
        return [OrganisationUnitView.model_validate(unit) for unit in units]

    async def routing_options(
        self,
        request_id: UUID,
        status: RequestStatus,
    ) -> list[OrganisationUnitView]:
        parent_position, expected_kind = _option_spec(status)
        if parent_position is None or expected_kind is None:
            return []
        parent_id = await self._session.scalar(
            select(RequestRouteSelection.unit_id).where(
                RequestRouteSelection.request_id == request_id,
                RequestRouteSelection.position == parent_position,
            )
        )
        if parent_id is None:
            return []
        units = (
            await self._session.scalars(
                select(OrganisationUnit)
                .where(
                    OrganisationUnit.parent_id == parent_id,
                    OrganisationUnit.kind == expected_kind,
                    OrganisationUnit.is_configured.is_(True),
                )
                .order_by(OrganisationUnit.sort_order, OrganisationUnit.id)
            )
        ).all()
        return [OrganisationUnitView.model_validate(unit) for unit in units]

    async def list_tracked_requests(self, actor: Actor) -> list[TrackedRequest]:
        membership = route_membership_condition(actor)
        if membership is None:
            return []
        request_rows = (
            await self._session.execute(
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
            await self._session.execute(
                select(
                    RequestRouteSelection.request_id,
                    RequestRouteSelection.position,
                    OrganisationUnit.id,
                    OrganisationUnit.name,
                    OrganisationUnit.kind,
                )
                .join(
                    OrganisationUnit,
                    OrganisationUnit.id == RequestRouteSelection.unit_id,
                )
                .where(RequestRouteSelection.request_id.in_(visible_ids))
                .order_by(RequestRouteSelection.position)
            )
        ).all()
        routes: dict[UUID, list[TrackedRouteUnit]] = defaultdict(list)
        for request_id, _position, unit_id, name, kind in route_rows:
            routes[request_id].append(
                TrackedRouteUnit(id=unit_id, name=name, kind=kind)
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


async def initialise_request_route(session: AsyncSession, request_id: UUID) -> None:
    root_id = await session.scalar(
        select(OrganisationUnit.id).where(
            OrganisationUnit.kind == OrganisationKind.ROOT,
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if root_id is None:
        raise RuntimeError("the organisation root is not configured")
    session.add(
        RequestRouteSelection(request_id=request_id, unit_id=root_id, position=0)
    )


async def resolve_routing_selection(
    session: AsyncSession,
    request: ServiceRequest,
    payload: CompletionPayload,
    *,
    lock: bool,
) -> RoutingSelection | None:
    spec = _routing_spec(request.status, payload)
    if spec is None:
        return None
    parent_id = await session.scalar(
        select(RequestRouteSelection.unit_id).where(
            RequestRouteSelection.request_id == request.id,
            RequestRouteSelection.position == spec.parent_position,
        )
    )
    if parent_id is None:
        raise InvalidAction("The request route is incomplete.")
    query = select(OrganisationUnit).where(
        OrganisationUnit.id == spec.destination_id,
        OrganisationUnit.parent_id == parent_id,
        OrganisationUnit.kind == spec.expected_kind,
        OrganisationUnit.is_configured.is_(True),
    )
    if lock:
        query = query.with_for_update()
    unit = await session.scalar(query)
    if unit is None:
        raise InvalidAction("Select a direct child of the current route.")
    groups = _candidate_groups(unit)
    return RoutingSelection(
        unit_id=unit.id,
        unit_code=unit.code,
        unit_name=unit.name,
        position=spec.selected_position,
        candidate_groups=groups,
        staffed=unit.staffing_status is StaffingStatus.STAFFED,
    )


async def apply_routing_selection(
    session: AsyncSession,
    request: ServiceRequest,
    routing: RoutingSelection | None,
) -> None:
    if routing is None:
        return
    await session.execute(
        delete(RequestRouteSelection).where(
            RequestRouteSelection.request_id == request.id,
            RequestRouteSelection.position >= routing.position,
        )
    )
    session.add(
        RequestRouteSelection(
            request_id=request.id,
            unit_id=routing.unit_id,
            position=routing.position,
        )
    )
    if routing.position == 1:
        request.command_group = routing.candidate_groups[0]
        request.ops_group = None
        _clear_team(request)
    elif routing.position == 2:
        request.ops_group = routing.candidate_groups[0]
        _clear_team(request)
    else:
        request.team_manager_group, request.team_analyst_group = (
            routing.candidate_groups
        )
        request.assigned_delivery_team = routing.unit_name
        request.assigned_specialist_id = None
        request.awaiting_team_staffing = not routing.staffed


async def clear_route_from(
    session: AsyncSession,
    request: ServiceRequest,
    position: int,
) -> None:
    await session.execute(
        delete(RequestRouteSelection).where(
            RequestRouteSelection.request_id == request.id,
            RequestRouteSelection.position >= position,
        )
    )
    if position <= 1:
        request.command_group = None
    if position <= 2:
        request.ops_group = None
    if position <= 3:
        _clear_team(request)


def route_membership_condition(actor: Actor) -> ColumnElement[bool] | None:
    position = ROUTE_POSITION_BY_ROLE.get(actor.role)
    if position is None:
        return None
    return exists().where(
        UserOrganisationMembership.user_id == actor.id,
        UserOrganisationMembership.unit_id == RequestRouteSelection.unit_id,
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
    position = ROUTE_POSITION_BY_ROLE.get(actor.role)
    if position is None:
        return True
    query = (
        select(UserOrganisationMembership.id)
        .join(
            RequestRouteSelection,
            RequestRouteSelection.unit_id == UserOrganisationMembership.unit_id,
        )
        .where(
            UserOrganisationMembership.user_id == actor.id,
            RequestRouteSelection.request_id == request_id,
            RequestRouteSelection.position == position,
        )
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query) is not None


def _option_spec(
    status: RequestStatus,
) -> tuple[int | None, OrganisationKind | None]:
    return {
        RequestStatus.TRIAGE_REVIEW: (0, OrganisationKind.COMMAND),
        RequestStatus.COORDINATION_REVIEW: (1, OrganisationKind.OPS_GROUP),
        RequestStatus.ALLOCATION_REVIEW: (2, OrganisationKind.TEAM),
    }.get(status, (None, None))


def _routing_spec(
    status: RequestStatus,
    payload: CompletionPayload,
) -> RoutingSpec | None:
    if status is RequestStatus.TRIAGE_REVIEW and isinstance(payload, ProgressRequest):
        return RoutingSpec(0, 1, OrganisationKind.COMMAND, payload.destination_unit_id)
    if status is RequestStatus.COORDINATION_REVIEW and isinstance(
        payload, SendToAllocation
    ):
        return RoutingSpec(
            1, 2, OrganisationKind.OPS_GROUP, payload.destination_unit_id
        )
    if status is RequestStatus.ALLOCATION_REVIEW and isinstance(
        payload, AllocateRequest
    ):
        return RoutingSpec(2, 3, OrganisationKind.TEAM, payload.destination_unit_id)
    return None


def _candidate_groups(unit: OrganisationUnit) -> tuple[str, ...]:
    groups = (
        (unit.manager_candidate_group, unit.analyst_candidate_group)
        if unit.kind is OrganisationKind.TEAM
        else (unit.routing_candidate_group,)
    )
    if any(group is None or GROUP_PATTERN.fullmatch(group) is None for group in groups):
        raise InvalidAction("The destination routing group is not configured safely.")
    return tuple(group for group in groups if group is not None)


def _clear_team(request: ServiceRequest) -> None:
    request.team_manager_group = None
    request.team_analyst_group = None
    request.assigned_delivery_team = None
    request.assigned_specialist_id = None
    request.awaiting_team_staffing = False
