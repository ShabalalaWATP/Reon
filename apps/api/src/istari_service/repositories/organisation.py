"""Organisation hierarchy, route validation and metadata-only tracking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, ServiceRequest, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
    StaffingStatus,
)
from istari_service.repositories.configuration_policies import (
    load_request_configuration_policy,
)
from istari_service.repositories.organisation_tracking import tracked_requests
from istari_service.repositories.routing_options import routing_workspace
from istari_service.request_participant_models import RequestParticipant
from istari_service.schemas.organisation import (
    OrganisationUnitView,
    RoutingOptionsWorkspace,
    TrackedRequest,
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
        return (await self.routing_workspace(request_id, status)).items

    async def routing_workspace(
        self,
        request_id: UUID,
        status: RequestStatus,
    ) -> RoutingOptionsWorkspace:
        return await routing_workspace(self._session, request_id, status)

    async def list_tracked_requests(self, actor: Actor) -> list[TrackedRequest]:
        items, _cursor = await self.page_tracked_requests(actor, limit=100, cursor=None)
        return items

    async def page_tracked_requests(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[TrackedRequest], str | None]:
        membership = route_membership_condition(actor)
        if membership is None:
            return [], None
        return await tracked_requests(
            self._session, membership, limit=limit, cursor=cursor
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
    policy = await load_request_configuration_policy(session, request.id)
    if policy is not None:
        return policy.routing_selection(
            parent_id=parent_id,
            destination_id=spec.destination_id,
            expected_kind=spec.expected_kind,
            selected_position=spec.selected_position,
        )
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
    await _end_request_participants(session, request)
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
        request.assigned_delivery_team_id = routing.unit_id
        request.assigned_specialist_id = None
        request.awaiting_team_staffing = not routing.staffed


async def clear_route_from(
    session: AsyncSession,
    request: ServiceRequest,
    position: int,
) -> None:
    if position <= 3:
        await _end_request_participants(session, request)
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
    request.assigned_delivery_team_id = None
    request.assigned_specialist_id = None
    request.awaiting_team_staffing = False


async def _end_request_participants(
    session: AsyncSession, request: ServiceRequest
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(RequestParticipant)
        .where(
            RequestParticipant.request_id == request.id,
            RequestParticipant.ended_at.is_(None),
        )
        .values(
            ended_at=now,
            end_reason="The delivery route changed.",
            version=RequestParticipant.version + 1,
        )
    )
