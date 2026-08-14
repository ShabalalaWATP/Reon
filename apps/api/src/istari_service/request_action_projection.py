"""Current-state action projection from authoritative request events."""

from __future__ import annotations

from datetime import UTC, datetime
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
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowTask,
)
from istari_service.organisation_models import RequestRouteSelection
from istari_service.qc_membership import QC_TEAM_ID
from istari_service.repositories.actions import SqlAlchemyActionRepository
from istari_service.repositories.request_participants import eligible_participant_ids
from istari_service.request_action_policy import (
    ACTION_BY_STATUS,
    ActionAudience,
    waiting_analyst,
)
from istari_service.request_action_policy import (
    action_link as _action_link,
)
from istari_service.request_action_policy import (
    action_section as _section,
)
from istari_service.request_action_policy import (
    action_source_type as _source_type,
)
from istari_service.request_action_policy import (
    terminal_status as _terminal,
)
from istari_service.request_event_models import RequestEvent

__all__ = [
    "ACTION_BY_STATUS",
    "ActionAudience",
    "_action_link",
    "_section",
    "action_audiences",
    "as_utc",
    "project_request_action",
    "waiting_analyst",
]


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
    waiting_ids = (
        set(await eligible_participant_ids(session, request))
        if request.status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        else set()
    )
    for waiting in waiting_ids:
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
        participant_ids = set(await eligible_participant_ids(session, request))
        return [
            ActionAudience(
                recipient_user_id=user_id,
                recipient_role=UserRole.DELIVERY_SPECIALIST,
                suffix=f"analyst:{user_id}",
            )
            for user_id in sorted(participant_ids, key=str)
        ]
    if status in {RequestStatus.QUALITY_REVIEW, RequestStatus.READY_FOR_RELEASE}:
        assignee_id = await _active_assignee(
            session, request.id, UserRole.QUALITY_RELEASE
        )
        if assignee_id is not None:
            return [
                ActionAudience(
                    recipient_user_id=assignee_id,
                    recipient_role=UserRole.QUALITY_RELEASE,
                    organisation_unit_id=QC_TEAM_ID,
                )
            ]
        return [
            ActionAudience(
                candidate_role=UserRole.QUALITY_RELEASE,
                organisation_unit_id=QC_TEAM_ID,
                suffix="quality:qc-team",
            )
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


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


_utc = as_utc
