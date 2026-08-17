"""Object access and server-derived destinations for request conversations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from mist_service.conversation_models import (
    ConversationTargetType,
    RequestConversation,
)
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound
from mist_service.models import RequestStatus, ServiceRequest, UserRole
from mist_service.organisation_models import OrganisationKind
from mist_service.policies import ROLE_BY_STAGE, has_self_request_conflict
from mist_service.request_event_audience import RequestEventAudience
from mist_service.schemas.conversations import ConversationTargetView
from mist_service.services.conversation_ports import (
    ConversationAccessReader,
    RouteMembershipReader,
)

QC_RELEVANT_STATUSES = frozenset(
    {
        RequestStatus.QUALITY_REVIEW,
        RequestStatus.READY_FOR_RELEASE,
        RequestStatus.COMPLETED,
    }
)
ROUTE_POSITION_BY_OWNER_ROLE = {
    UserRole.INTAKE_TRIAGE: 0,
    UserRole.SERVICE_COORDINATION: 1,
    UserRole.OPERATIONS_ALLOCATION: 2,
}


@dataclass(frozen=True, slots=True)
class ResolvedConversationTarget:
    type: ConversationTargetType
    unit_id: UUID | None
    label: str


@dataclass(frozen=True, slots=True)
class ConversationAudienceScope:
    customer_only: bool
    allowed_targets: frozenset[ConversationTargetType]
    route_unit_ids: frozenset[UUID]


class ConversationAccess:
    def __init__(
        self,
        repository: ConversationAccessReader,
        route_memberships: RouteMembershipReader,
    ) -> None:
        self._repository = repository
        self._route_memberships = route_memberships

    async def authorised_request(
        self, actor: Actor, request_id: UUID
    ) -> ServiceRequest:
        request = await self._repository.request(request_id)
        if (
            request is None
            or not await self._repository.active_actor(actor)
            or actor.role is UserRole.PLATFORM_ADMIN
            or has_self_request_conflict(actor, request)
        ):
            raise ObjectNotFound()
        if actor.role is UserRole.REQUESTER:
            if request.requester_id != actor.id:
                raise ObjectNotFound()
            return request
        route_member = await self._route_memberships.has_route_membership(
            actor, request_id
        )
        participant = await self._repository.is_active_participant(request, actor)
        team_manager = await self._repository.is_active_team_manager(request, actor)
        qc_access = await self._has_qc_access(actor, request.status)
        if not route_member and not participant and not team_manager and not qc_access:
            raise ObjectNotFound()
        return request

    async def audience_scope(
        self, actor: Actor, request: ServiceRequest
    ) -> ConversationAudienceScope:
        if actor.role is UserRole.REQUESTER:
            return ConversationAudienceScope(True, frozenset(), frozenset())
        allowed: set[ConversationTargetType] = set()
        if actor.id in await self._current_owner_ids(request):
            allowed.add(ConversationTargetType.CURRENT_OWNER)
        if await self._repository.is_active_team_manager(request, actor):
            allowed.add(ConversationTargetType.TEAM_MANAGERS)
        if await self._repository.is_active_participant(request, actor):
            allowed.add(ConversationTargetType.ASSIGNED_ANALYSTS)
        if await self._has_qc_access(actor, request.status):
            allowed.add(ConversationTargetType.QC_TEAM)
        selected_units = {
            unit.id
            for unit, _position in await self._repository.selected_route(request.id)
        }
        return ConversationAudienceScope(
            False,
            frozenset(allowed),
            frozenset(selected_units & set(actor.organisation_unit_ids)),
        )

    async def can_access_conversation(
        self,
        actor: Actor,
        request: ServiceRequest,
        conversation: RequestConversation,
    ) -> bool:
        scope = await self.audience_scope(actor, request)
        if conversation.visibility is RequestEventAudience.CUSTOMER_AND_STAFF:
            return True
        if scope.customer_only:
            return False
        if conversation.target_type is ConversationTargetType.ROUTE_UNIT:
            return conversation.target_unit_id in scope.route_unit_ids
        return conversation.target_type in scope.allowed_targets

    async def allowed_targets(
        self, actor: Actor, request: ServiceRequest
    ) -> list[ConversationTargetView]:
        if actor.role is UserRole.REQUESTER:
            return [
                ConversationTargetView(
                    type=ConversationTargetType.CURRENT_OWNER,
                    label=request.current_owner,
                )
            ]
        targets = [
            ConversationTargetView(
                type=ConversationTargetType.CUSTOMER, label="Customer"
            ),
            ConversationTargetView(
                type=ConversationTargetType.CURRENT_OWNER,
                label=request.current_owner,
            ),
        ]
        route = await self._repository.selected_route(request.id)
        targets.extend(
            ConversationTargetView(
                type=ConversationTargetType.ROUTE_UNIT,
                unit_id=unit.id,
                label=unit.name,
            )
            for unit, _position in route
            if unit.kind is not OrganisationKind.TEAM
        )
        if request.assigned_delivery_team_id is not None:
            targets.extend(
                [
                    ConversationTargetView(
                        type=ConversationTargetType.TEAM_MANAGERS,
                        label=(
                            f"{request.assigned_delivery_team or 'Assigned team'} "
                            "Managers"
                        ),
                    ),
                    ConversationTargetView(
                        type=ConversationTargetType.ASSIGNED_ANALYSTS,
                        label="Assigned Analysts",
                    ),
                ]
            )
        if request.status in QC_RELEVANT_STATUSES:
            targets.append(
                ConversationTargetView(
                    type=ConversationTargetType.QC_TEAM,
                    label="QC Team",
                )
            )
        return targets

    async def resolve_target(
        self,
        actor: Actor,
        request: ServiceRequest,
        target_type: ConversationTargetType,
        target_unit_id: UUID | None,
    ) -> ResolvedConversationTarget:
        targets = await self.allowed_targets(actor, request)
        selected = next(
            (
                target
                for target in targets
                if target.type is target_type and target.unit_id == target_unit_id
            ),
            None,
        )
        if selected is None:
            raise ObjectNotFound()
        return ResolvedConversationTarget(
            type=selected.type,
            unit_id=selected.unit_id,
            label=selected.label,
        )

    async def recipient_ids(
        self,
        request: ServiceRequest,
        target: ResolvedConversationTarget,
    ) -> set[UUID]:
        if target.type is ConversationTargetType.CUSTOMER:
            return {request.requester_id}
        if target.type is ConversationTargetType.TEAM_MANAGERS:
            return await self._team_managers(request)
        if target.type is ConversationTargetType.ASSIGNED_ANALYSTS:
            return await self._repository.active_participant_ids(request)
        if target.type is ConversationTargetType.ROUTE_UNIT:
            if target.unit_id is None:  # pragma: no cover - schema invariant
                raise ObjectNotFound()
            route_position = next(
                (
                    position
                    for unit, position in await self._repository.selected_route(
                        request.id
                    )
                    if unit.id == target.unit_id
                ),
                None,
            )
            route_role = next(
                (
                    role
                    for role, position in ROUTE_POSITION_BY_OWNER_ROLE.items()
                    if position == route_position
                ),
                None,
            )
            return (
                await self._repository.active_unit_member_ids(
                    target.unit_id, route_role
                )
                if route_role is not None
                else set()
            )
        if target.type is ConversationTargetType.QC_TEAM:
            return await self._repository.active_qc_ids(
                manager_only=request.status
                in {RequestStatus.READY_FOR_RELEASE, RequestStatus.COMPLETED}
            )
        return await self._current_owner_ids(request)

    async def _current_owner_ids(self, request: ServiceRequest) -> set[UUID]:
        if request.status in {
            RequestStatus.INFORMATION_REQUIRED,
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            RequestStatus.COMPLETED,
        }:
            return {request.requester_id}
        role = ROLE_BY_STAGE.get(request.status)
        if role is None:
            return set()
        if role is UserRole.DELIVERY_SPECIALIST:
            return await self._repository.active_participant_ids(request)
        if role is UserRole.DELIVERY_TEAM_LEAD:
            return await self._team_managers(request)
        if role is UserRole.QUALITY_RELEASE:
            return await self._repository.active_qc_ids(
                manager_only=request.status is RequestStatus.READY_FOR_RELEASE
            )
        position = ROUTE_POSITION_BY_OWNER_ROLE.get(role)
        if position is None:
            return set()
        unit = next(
            (
                unit
                for unit, route_position in await self._repository.selected_route(
                    request.id
                )
                if route_position == position
            ),
            None,
        )
        return (
            await self._repository.active_unit_member_ids(unit.id, role)
            if unit is not None
            else set()
        )

    async def _team_managers(self, request: ServiceRequest) -> set[UUID]:
        if request.assigned_delivery_team_id is None:
            return set()
        return await self._repository.active_team_manager_ids(
            request.assigned_delivery_team_id
        )

    async def _has_qc_access(self, actor: Actor, status: RequestStatus) -> bool:
        if status is RequestStatus.QUALITY_REVIEW:
            return await self._repository.is_active_qc_member(actor)
        if status in {RequestStatus.READY_FOR_RELEASE, RequestStatus.COMPLETED}:
            return await self._repository.is_active_qc_manager(actor)
        return False
