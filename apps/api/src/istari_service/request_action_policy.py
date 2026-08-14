"""Framework-free presentation policy for request action projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from istari_service.action_notification_models import (
    ActionSection,
    ActionSourceType,
)
from istari_service.models import RequestStatus, ServiceRequest, UserRole


@dataclass(frozen=True, slots=True)
class ActionAudience:
    recipient_user_id: UUID | None = None
    recipient_role: UserRole | None = None
    candidate_role: UserRole | None = None
    required_scope: str | None = None
    organisation_unit_id: UUID | None = None
    suffix: str = "current"


ACTION_BY_STATUS = {
    RequestStatus.ROUTING_PENDING: (UserRole.INTAKE_TRIAGE, 0, "REVIEW_SUBMISSION"),
    RequestStatus.TRIAGE_REVIEW: (UserRole.INTAKE_TRIAGE, 0, "REVIEW_SUBMISSION"),
    RequestStatus.COORDINATION_REVIEW: (
        UserRole.SERVICE_COORDINATION,
        1,
        "CHOOSE_OPS_GROUP",
    ),
    RequestStatus.ON_HOLD: (UserRole.SERVICE_COORDINATION, 1, "REVIEW_HELD_REQUEST"),
    RequestStatus.ALLOCATION_REVIEW: (
        UserRole.OPERATIONS_ALLOCATION,
        2,
        "CHOOSE_DELIVERY_TEAM",
    ),
    RequestStatus.DELIVERY_PLANNING: (
        UserRole.DELIVERY_TEAM_LEAD,
        3,
        "ASSIGN_ANALYST",
    ),
    RequestStatus.LEAD_REVIEW: (
        UserRole.DELIVERY_TEAM_LEAD,
        3,
        "MANAGER_REVIEW",
    ),
}

QUEUE_BY_ROLE = {
    UserRole.INTAKE_TRIAGE: "/triage",
    UserRole.SERVICE_COORDINATION: "/coordination",
    UserRole.OPERATIONS_ALLOCATION: "/allocation",
    UserRole.DELIVERY_TEAM_LEAD: "/delivery/team",
    UserRole.DELIVERY_SPECIALIST: "/delivery/my-work",
    UserRole.QUALITY_RELEASE: "/quality-release",
}


def action_link(request: ServiceRequest, audience: ActionAudience) -> str:
    role = audience.candidate_role or audience.recipient_role
    if role is None and request.status in ACTION_BY_STATUS:
        role = ACTION_BY_STATUS[request.status][0]
    if role is None and request.status in {
        RequestStatus.QUALITY_REVIEW,
        RequestStatus.READY_FOR_RELEASE,
    }:
        role = UserRole.QUALITY_RELEASE
    if role is None and request.status in {
        RequestStatus.IN_PROGRESS,
        RequestStatus.REWORK_REQUIRED,
    }:
        role = UserRole.DELIVERY_SPECIALIST
    queue = QUEUE_BY_ROLE.get(role) if role is not None else None
    return (
        f"{queue}?requestId={request.id}"
        if queue is not None
        else f"/requests/{request.id}"
    )


def waiting_analyst(request: ServiceRequest) -> UUID | None:
    return (
        request.assigned_specialist_id
        if request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        else None
    )


def action_section(
    request: ServiceRequest,
    changed_at: datetime,
    action_type: str | None = None,
) -> ActionSection:
    if terminal_status(request.status):
        return (
            ActionSection.NEEDS_MY_ACTION
            if request.status is RequestStatus.COMPLETED
            and action_type != "RECENTLY_COMPLETED"
            else ActionSection.RECENTLY_COMPLETED
        )
    if request.status is RequestStatus.ON_HOLD or request.awaiting_team_staffing:
        return ActionSection.WAITING
    if request.required_by <= changed_at.date() + timedelta(days=3):
        return ActionSection.DUE_SOON
    return ActionSection.NEEDS_MY_ACTION


def action_source_type(status: RequestStatus) -> ActionSourceType:
    if status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        return ActionSourceType.CLARIFICATION
    if status is RequestStatus.COMPLETED:
        return ActionSourceType.FEEDBACK
    return ActionSourceType.WORKFLOW_TASK


def terminal_status(status: RequestStatus) -> bool:
    return status in {
        RequestStatus.COMPLETED,
        RequestStatus.CLOSED_NOT_PROGRESSED,
        RequestStatus.CANCELLED,
    }
