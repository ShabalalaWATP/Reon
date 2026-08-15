"""Framework-free work discovery, claim and completion policy."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.authorisation import (
    ALLOW,
    PolicyDecision,
    PolicyDenial,
    WorkOperation,
    deny,
)
from mist_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from mist_service.request_access_policy import (
    ActorLike,
    RequestLike,
    can_access_work,
)


class WorkLike(Protocol):
    @property
    def request(self) -> RequestLike: ...

    @property
    def task_status(self) -> WorkflowTaskStatus: ...

    @property
    def assignee_id(self) -> UUID | None: ...

    @property
    def completed_at(self) -> datetime | None: ...


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


def allowed_actions(
    actor: ActorLike,
    request: RequestLike,
    *,
    pool_membership_verified: bool = False,
) -> tuple[str, ...]:
    if not can_access_work(
        actor, request, pool_membership_verified=pool_membership_verified
    ):
        return ()
    return ACTIONS_BY_STAGE.get(request.status, ())


def may_claim(
    actor: ActorLike,
    request: RequestLike,
    *,
    pool_membership_verified: bool = False,
) -> bool:
    """Only shared decision roles claim work; Analysts receive named assignments."""
    return actor.role in CLAIMABLE_ROLES and can_access_work(
        actor, request, pool_membership_verified=pool_membership_verified
    )


def may_complete(
    actor: ActorLike,
    request: RequestLike,
    action: str,
    assignee_id: UUID | None,
    *,
    pool_membership_verified: bool = False,
) -> bool:
    """Compatibility predicate derived from the typed completion policy."""
    return decide_work_completion(
        actor,
        request,
        action,
        assignee_id,
        pool_membership_verified=pool_membership_verified,
    ).allowed


def decide_work_access(
    actor: ActorLike,
    work: WorkLike,
    operation: WorkOperation | str,
    *,
    pool_membership_verified: bool = False,
) -> PolicyDecision:
    """Decide whether an actor may discover or address one active work item."""
    if work.completed_at is not None:
        return deny(PolicyDenial.WORK_STATE)
    if not can_access_work(
        actor, work.request, pool_membership_verified=pool_membership_verified
    ):
        return deny(PolicyDenial.OBJECT_SCOPE)
    if not _work_is_visible(
        actor, work, pool_membership_verified=pool_membership_verified
    ):
        return deny(PolicyDenial.ASSIGNMENT)
    if operation in {WorkOperation.VIEW, WorkOperation.COMPLETE}:
        return ALLOW
    if operation is WorkOperation.CLAIM:
        return (
            ALLOW
            if may_claim(
                actor,
                work.request,
                pool_membership_verified=pool_membership_verified,
            )
            else deny(PolicyDenial.ROLE)
        )
    if operation is WorkOperation.LIST_ELIGIBLE_SPECIALISTS:
        return _specialist_list_decision(actor, work.request)
    if operation is WorkOperation.VIEW_ROUTING_OPTIONS:
        return (
            ALLOW if work.request.status in ROUTING_STAGES else deny(PolicyDenial.STAGE)
        )
    return deny(PolicyDenial.ACTION)


def _work_is_visible(
    actor: ActorLike,
    work: WorkLike,
    *,
    pool_membership_verified: bool,
) -> bool:
    if work.task_status is WorkflowTaskStatus.OPEN:
        return work.assignee_id is None and may_claim(
            actor, work.request, pool_membership_verified=pool_membership_verified
        )
    return work.assignee_id == actor.id or (
        actor.role is UserRole.DELIVERY_SPECIALIST
        and actor.id in getattr(work.request, "participant_ids", frozenset())
    )


def _specialist_list_decision(actor: ActorLike, request: RequestLike) -> PolicyDecision:
    if actor.role is not UserRole.DELIVERY_TEAM_LEAD:
        return deny(PolicyDenial.ROLE)
    if request.status is not RequestStatus.DELIVERY_PLANNING:
        return deny(PolicyDenial.STAGE)
    return (
        ALLOW
        if request.assigned_delivery_team is not None
        else deny(PolicyDenial.OBJECT_SCOPE)
    )


def decide_work_completion(
    actor: ActorLike,
    request: RequestLike,
    action: str,
    assignee_id: UUID | None,
    *,
    pool_membership_verified: bool = False,
) -> PolicyDecision:
    """Decide a completion after work visibility and task state are established."""
    if not can_access_work(
        actor, request, pool_membership_verified=pool_membership_verified
    ):
        return deny(PolicyDenial.OBJECT_SCOPE)
    shared_analyst_assignment = (
        actor.role is UserRole.DELIVERY_SPECIALIST
        and actor.id in getattr(request, "participant_ids", frozenset())
    )
    if assignee_id != actor.id and not shared_analyst_assignment:
        return deny(PolicyDenial.ASSIGNMENT)
    return (
        ALLOW
        if action
        in allowed_actions(
            actor, request, pool_membership_verified=pool_membership_verified
        )
        else deny(PolicyDenial.ACTION)
    )
