"""Current-state action projection from authoritative request events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ActionSourceType,
    ProjectionHealth,
)
from istari_service.models import (
    Feedback,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowTask,
)
from istari_service.organisation_models import RequestRouteSelection
from istari_service.repositories.actions import SqlAlchemyActionRepository


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


async def project_request_action(
    session: AsyncSession, event: RequestEvent, request: ServiceRequest
) -> None:
    actions = SqlAlchemyActionRepository(session)
    projected_at = _utc(event.created_at)
    active_keys: list[str] = []
    action_type = await _action_type(session, request)
    for audience in await action_audiences(session, request):
        key = f"request:{request.id}:{audience.suffix}"
        active_keys.append(key)
        await actions.project_action(
            stable_key=key,
            source_type=_source_type(request.status),
            source_id=str(event.id),
            source_version=request.audit_event_count,
            request_id=request.id,
            recipient_user_id=audience.recipient_user_id,
            candidate_role=audience.candidate_role,
            required_scope=audience.required_scope,
            organisation_unit_id=audience.organisation_unit_id,
            section=_section(request, projected_at, action_type),
            action_type=action_type,
            reference=request.reference,
            safe_title=request.title,
            current_owner=request.current_owner,
            required_by=request.required_by,
            last_changed_at=projected_at,
            completed_at=(projected_at if _terminal(request.status) else None),
            deep_link=_action_link(request, audience),
            projected_at=projected_at,
        )
    waiting = waiting_analyst(request)
    if waiting is not None:
        key = f"request:{request.id}:waiting:{waiting}"
        active_keys.append(key)
        await actions.project_action(
            stable_key=key,
            source_type=ActionSourceType.CLARIFICATION,
            source_id=str(event.id),
            source_version=request.audit_event_count,
            request_id=request.id,
            recipient_user_id=waiting,
            candidate_role=None,
            required_scope=None,
            organisation_unit_id=None,
            section=ActionSection.WAITING,
            action_type="WAITING_FOR_CLARIFICATION",
            reference=request.reference,
            safe_title=request.title,
            current_owner="Customer",
            required_by=request.required_by,
            last_changed_at=projected_at,
            completed_at=None,
            deep_link=f"/delivery/my-work?requestId={request.id}",
            projected_at=projected_at,
        )
    await session.execute(
        update(ActionProjection)
        .where(
            ActionProjection.request_id == request.id,
            ActionProjection.stable_key.not_in(active_keys),
            ActionProjection.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await actions.update_checkpoint(
        "actions",
        last_event_key=event.event_hash,
        source_changed_at=projected_at,
        projected_at=projected_at,
        pending_count=0,
        failed_count=0,
        health=ProjectionHealth.CURRENT,
    )


async def action_audiences(
    session: AsyncSession, request: ServiceRequest
) -> list[ActionAudience]:
    status = request.status
    if status in {
        RequestStatus.INFORMATION_REQUIRED,
        RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        RequestStatus.COMPLETED,
        RequestStatus.CLOSED_NOT_PROGRESSED,
        RequestStatus.CANCELLED,
    }:
        return [
            ActionAudience(
                recipient_user_id=request.requester_id,
                recipient_role=UserRole.REQUESTER,
            )
        ]
    if status in {RequestStatus.IN_PROGRESS, RequestStatus.REWORK_REQUIRED}:
        return (
            [
                ActionAudience(
                    recipient_user_id=request.assigned_specialist_id,
                    recipient_role=UserRole.DELIVERY_SPECIALIST,
                )
            ]
            if request.assigned_specialist_id
            else []
        )
    if status in {RequestStatus.QUALITY_REVIEW, RequestStatus.READY_FOR_RELEASE}:
        assignee_id = await _active_assignee(
            session, request.id, UserRole.QUALITY_RELEASE
        )
        if assignee_id is not None:
            return [
                ActionAudience(
                    recipient_user_id=assignee_id,
                    recipient_role=UserRole.QUALITY_RELEASE,
                )
            ]
        scopes = list(
            await session.scalars(
                select(User.scope)
                .where(
                    User.role == UserRole.QUALITY_RELEASE,
                    User.is_active.is_(True),
                )
                .distinct()
            )
        )
        return [
            ActionAudience(
                candidate_role=UserRole.QUALITY_RELEASE,
                required_scope=scope,
                suffix=f"quality:{scope}",
            )
            for scope in scopes
        ]
    spec = ACTION_BY_STATUS.get(status)
    if spec is None:
        return []
    role, position, _action = spec
    assignee_id = await _active_assignee(session, request.id, role)
    if assignee_id is not None:
        return [ActionAudience(recipient_user_id=assignee_id, recipient_role=role)]
    unit_id = await session.scalar(
        select(RequestRouteSelection.unit_id).where(
            RequestRouteSelection.request_id == request.id,
            RequestRouteSelection.position == position,
        )
    )
    return (
        [ActionAudience(candidate_role=role, organisation_unit_id=unit_id)]
        if unit_id
        else []
    )


async def _active_assignee(
    session: AsyncSession, request_id: UUID, role: UserRole
) -> UUID | None:
    return await session.scalar(
        select(WorkflowTask.assignee_user_id)
        .where(
            WorkflowTask.request_id == request_id,
            WorkflowTask.candidate_role == role,
            WorkflowTask.completed_at.is_(None),
        )
        .order_by(WorkflowTask.updated_at.desc())
        .limit(1)
    )


def _action_link(request: ServiceRequest, audience: ActionAudience) -> str:
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


async def _action_type(session: AsyncSession, request: ServiceRequest) -> str:
    if request.status is RequestStatus.INFORMATION_REQUIRED:
        return "PROVIDE_INFORMATION"
    if request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        return "PROVIDE_CLARIFICATION"
    if request.status in {RequestStatus.IN_PROGRESS, RequestStatus.REWORK_REQUIRED}:
        return "DEVELOP_PRODUCT"
    if request.status is RequestStatus.QUALITY_REVIEW:
        return "QC_REVIEW"
    if request.status is RequestStatus.READY_FOR_RELEASE:
        return "DISSEMINATE_PRODUCT"
    if request.status is RequestStatus.COMPLETED:
        feedback = await session.scalar(
            select(Feedback.id).where(Feedback.request_id == request.id)
        )
        return "RECENTLY_COMPLETED" if feedback else "FEEDBACK_DUE"
    if request.status in {
        RequestStatus.CLOSED_NOT_PROGRESSED,
        RequestStatus.CANCELLED,
    }:
        return "RECENTLY_COMPLETED"
    return ACTION_BY_STATUS.get(request.status, (None, None, "REVIEW_REQUEST"))[2]


def _section(
    request: ServiceRequest,
    changed_at: datetime,
    action_type: str | None = None,
) -> ActionSection:
    if _terminal(request.status):
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


def _source_type(status: RequestStatus) -> ActionSourceType:
    if status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        return ActionSourceType.CLARIFICATION
    if status is RequestStatus.COMPLETED:
        return ActionSourceType.FEEDBACK
    return ActionSourceType.WORKFLOW_TASK


def _terminal(status: RequestStatus) -> bool:
    return status in {
        RequestStatus.COMPLETED,
        RequestStatus.CLOSED_NOT_PROGRESSED,
        RequestStatus.CANCELLED,
    }


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


_utc = as_utc
