"""Central role, stage and object-level access policy."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.authorisation import (
    ALLOW,
    PolicyDecision,
    PolicyDenial,
    RequestOperation,
    WorkOperation,
    deny,
)
from istari_service.models import (
    RequestStatus,
    UserRole,
    WorkflowTaskStatus,
)


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


class WorkLike(Protocol):
    @property
    def request(self) -> RequestLike: ...

    @property
    def task_status(self) -> WorkflowTaskStatus: ...

    @property
    def assignee_id(self) -> UUID | None: ...

    @property
    def completed_at(self) -> datetime | None: ...


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


CLAIMABLE_ROLES = frozenset(
    {
        UserRole.INTAKE_TRIAGE,
        UserRole.SERVICE_COORDINATION,
        UserRole.OPERATIONS_ALLOCATION,
        UserRole.DELIVERY_TEAM_LEAD,
        UserRole.QUALITY_RELEASE,
    }
)

ROUTING_STAGES = frozenset(
    {
        RequestStatus.TRIAGE_REVIEW,
        RequestStatus.COORDINATION_REVIEW,
        RequestStatus.ALLOCATION_REVIEW,
    }
)


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


def _request_is_visible(actor: ActorLike, request: RequestLike) -> bool:
    if actor.role == UserRole.REQUESTER:
        return request.requester_id == actor.id
    if actor.role is UserRole.DELIVERY_SPECIALIST and actor.id in getattr(
        request, "participant_ids", frozenset()
    ):
        return True
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        return (
            request.assigned_delivery_team_id in actor.organisation_unit_ids
            if request.assigned_delivery_team_id is not None
            else request.assigned_delivery_team == actor.scope
        )
    if (
        request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        and actor.role is UserRole.DELIVERY_SPECIALIST
    ):
        return request.assigned_specialist_id == actor.id
    return can_access_work(actor, request)


def decide_request_access(
    actor: ActorLike,
    operation: RequestOperation | str,
    request: RequestLike | None = None,
) -> PolicyDecision:
    """Decide one request operation without exposing the denial category."""

    if operation in {RequestOperation.CREATE, RequestOperation.LIST}:
        return ALLOW if actor.role is UserRole.REQUESTER else deny(PolicyDenial.ROLE)
    if request is None:
        return deny(PolicyDenial.OBJECT_SCOPE)
    if operation is RequestOperation.VIEW:
        return (
            ALLOW
            if _request_is_visible(actor, request)
            else deny(PolicyDenial.OBJECT_SCOPE)
        )
    if operation in {
        RequestOperation.CANCEL,
        RequestOperation.FEEDBACK,
        RequestOperation.DOWNLOAD_PRODUCT,
    }:
        if actor.role is not UserRole.REQUESTER:
            return deny(PolicyDenial.ROLE)
        return (
            ALLOW
            if request.requester_id == actor.id
            else deny(PolicyDenial.OBJECT_SCOPE)
        )
    if not _request_is_visible(actor, request):
        return deny(PolicyDenial.OBJECT_SCOPE)
    if operation is RequestOperation.VIEW_UNRELEASED_PRODUCT:
        return (
            ALLOW if actor.role is not UserRole.REQUESTER else deny(PolicyDenial.ROLE)
        )
    if operation is RequestOperation.VIEW_CLARIFICATIONS:
        return (
            ALLOW
            if actor.role
            in {
                UserRole.REQUESTER,
                UserRole.DELIVERY_SPECIALIST,
                UserRole.DELIVERY_TEAM_LEAD,
            }
            else deny(PolicyDenial.ROLE)
        )
    return deny(PolicyDenial.ACTION)


def can_view_request(actor: ActorLike, request: RequestLike) -> bool:
    """Compatibility predicate derived from the typed request policy."""

    return decide_request_access(actor, RequestOperation.VIEW, request).allowed


def allowed_actions(actor: ActorLike, request: RequestLike) -> tuple[str, ...]:
    if not can_access_work(actor, request):
        return ()
    return ACTIONS_BY_STAGE.get(request.status, ())


def may_claim(actor: ActorLike, request: RequestLike) -> bool:
    """Only shared decision roles claim work; Analysts receive named assignments."""

    return actor.role in CLAIMABLE_ROLES and can_access_work(actor, request)


def may_complete(
    actor: ActorLike,
    request: RequestLike,
    action: str,
    assignee_id: UUID | None,
) -> bool:
    """Compatibility predicate derived from the typed completion policy."""

    return decide_work_completion(actor, request, action, assignee_id).allowed


def decide_work_access(
    actor: ActorLike,
    work: WorkLike,
    operation: WorkOperation | str,
) -> PolicyDecision:
    """Decide whether an actor may discover or address one active work item."""

    if work.completed_at is not None:
        return deny(PolicyDenial.WORK_STATE)
    if not can_access_work(actor, work.request):
        return deny(PolicyDenial.OBJECT_SCOPE)
    if work.task_status is WorkflowTaskStatus.OPEN:
        visible = work.assignee_id is None and may_claim(actor, work.request)
    else:
        visible = work.assignee_id == actor.id
    if not visible:
        return deny(PolicyDenial.ASSIGNMENT)
    if operation in {WorkOperation.VIEW, WorkOperation.COMPLETE}:
        return ALLOW
    if operation is WorkOperation.CLAIM:
        return ALLOW if may_claim(actor, work.request) else deny(PolicyDenial.ROLE)
    if operation is WorkOperation.LIST_ELIGIBLE_SPECIALISTS:
        if actor.role is not UserRole.DELIVERY_TEAM_LEAD:
            return deny(PolicyDenial.ROLE)
        if work.request.status is not RequestStatus.DELIVERY_PLANNING:
            return deny(PolicyDenial.STAGE)
        return (
            ALLOW
            if work.request.assigned_delivery_team is not None
            else deny(PolicyDenial.OBJECT_SCOPE)
        )
    if operation is WorkOperation.VIEW_ROUTING_OPTIONS:
        return (
            ALLOW if work.request.status in ROUTING_STAGES else deny(PolicyDenial.STAGE)
        )
    return deny(PolicyDenial.ACTION)


def decide_work_completion(
    actor: ActorLike,
    request: RequestLike,
    action: str,
    assignee_id: UUID | None,
) -> PolicyDecision:
    """Decide a completion after work visibility and task state are established."""

    if not can_access_work(actor, request):
        return deny(PolicyDenial.OBJECT_SCOPE)
    if assignee_id != actor.id:
        return deny(PolicyDenial.ASSIGNMENT)
    return (
        ALLOW
        if action in allowed_actions(actor, request)
        else deny(PolicyDenial.ACTION)
    )
