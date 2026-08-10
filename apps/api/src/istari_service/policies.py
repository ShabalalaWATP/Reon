"""Central role, stage and object-level access policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from istari_service.models import RequestStatus, UserRole


class ActorLike(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def role(self) -> UserRole: ...

    @property
    def scope(self) -> str: ...

    @property
    def organisation_unit_ids(self) -> frozenset[UUID]: ...


class RequestLike(Protocol):
    @property
    def requester_id(self) -> UUID: ...

    @property
    def status(self) -> RequestStatus: ...

    @property
    def assigned_delivery_team(self) -> str | None: ...

    @property
    def assigned_delivery_team_id(self) -> UUID | None: ...

    @property
    def assigned_specialist_id(self) -> UUID | None: ...


ROLE_BY_STAGE: Mapping[RequestStatus, UserRole] = {
    RequestStatus.TRIAGE_REVIEW: UserRole.INTAKE_TRIAGE,
    RequestStatus.INFORMATION_REQUIRED: UserRole.REQUESTER,
    RequestStatus.COORDINATION_REVIEW: UserRole.SERVICE_COORDINATION,
    RequestStatus.ON_HOLD: UserRole.SERVICE_COORDINATION,
    RequestStatus.ALLOCATION_REVIEW: UserRole.OPERATIONS_ALLOCATION,
    RequestStatus.DELIVERY_PLANNING: UserRole.DELIVERY_TEAM_LEAD,
    RequestStatus.IN_PROGRESS: UserRole.DELIVERY_SPECIALIST,
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: UserRole.REQUESTER,
    RequestStatus.LEAD_REVIEW: UserRole.DELIVERY_TEAM_LEAD,
    RequestStatus.REWORK_REQUIRED: UserRole.DELIVERY_SPECIALIST,
    RequestStatus.QUALITY_REVIEW: UserRole.QUALITY_RELEASE,
    RequestStatus.READY_FOR_RELEASE: UserRole.QUALITY_RELEASE,
}


ACTIONS_BY_STAGE: Mapping[RequestStatus, tuple[str, ...]] = {
    RequestStatus.TRIAGE_REVIEW: ("request_information", "progress", "close"),
    RequestStatus.INFORMATION_REQUIRED: ("provide_information", "withdraw"),
    RequestStatus.COORDINATION_REVIEW: (
        "send_to_allocation",
        "return_to_triage",
        "hold",
        "close",
    ),
    RequestStatus.ON_HOLD: ("resume", "close"),
    RequestStatus.ALLOCATION_REVIEW: ("allocate", "return_to_coordination"),
    RequestStatus.DELIVERY_PLANNING: ("assign", "return_for_reallocation"),
    RequestStatus.IN_PROGRESS: ("submit", "request_clarification"),
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: (
        "provide_clarification",
        "withdraw",
    ),
    RequestStatus.REWORK_REQUIRED: ("submit", "request_clarification"),
    RequestStatus.LEAD_REVIEW: ("approve", "changes_required"),
    RequestStatus.QUALITY_REVIEW: ("approve", "changes_required"),
    RequestStatus.READY_FOR_RELEASE: ("release",),
}


def has_stage_role(actor: ActorLike, request: RequestLike) -> bool:
    """Return whether the actor holds the exact role for the current stage."""

    return ROLE_BY_STAGE.get(request.status) == actor.role


def is_object_scoped(actor: ActorLike, request: RequestLike) -> bool:
    """Apply ownership, team and assignment restrictions after role matching."""

    if actor.role == UserRole.REQUESTER:
        return request.requester_id == actor.id
    if actor.role == UserRole.DELIVERY_TEAM_LEAD:
        return (
            request.assigned_delivery_team_id in actor.organisation_unit_ids
            if request.assigned_delivery_team_id is not None
            else request.assigned_delivery_team == actor.scope
        )
    if actor.role == UserRole.DELIVERY_SPECIALIST:
        return request.assigned_specialist_id == actor.id
    return actor.role in {
        UserRole.INTAKE_TRIAGE,
        UserRole.SERVICE_COORDINATION,
        UserRole.OPERATIONS_ALLOCATION,
        UserRole.QUALITY_RELEASE,
    }


def can_access_work(actor: ActorLike, request: RequestLike) -> bool:
    """Work visibility always requires both role and object scope."""

    return has_stage_role(actor, request) and is_object_scoped(actor, request)


def can_view_request(actor: ActorLike, request: RequestLike) -> bool:
    """Requesters see their own objects; staff see only applicable work."""

    if actor.role == UserRole.REQUESTER:
        return request.requester_id == actor.id
    if actor.role is UserRole.DELIVERY_SPECIALIST and actor.id in getattr(
        request, "participant_ids", frozenset()
    ):
        return True
    if request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        if actor.role is UserRole.DELIVERY_SPECIALIST:
            return request.assigned_specialist_id == actor.id
        if actor.role is UserRole.DELIVERY_TEAM_LEAD:
            return (
                request.assigned_delivery_team_id in actor.organisation_unit_ids
                if request.assigned_delivery_team_id is not None
                else request.assigned_delivery_team == actor.scope
            )
    return can_access_work(actor, request)


def allowed_actions(actor: ActorLike, request: RequestLike) -> tuple[str, ...]:
    if not can_access_work(actor, request):
        return ()
    return ACTIONS_BY_STAGE.get(request.status, ())


def may_complete(
    actor: ActorLike,
    request: RequestLike,
    action: str,
    assignee_id: UUID | None,
) -> bool:
    """Completion requires current scope, an allowed action and a claimed task."""

    return action in allowed_actions(actor, request) and assignee_id == actor.id
