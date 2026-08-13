"""Object-level visibility predicates for projected personal actions."""

from sqlalchemy import ColumnElement, and_, exists, false, or_

from istari_service.action_notification_models import ActionProjection
from istari_service.domain import Actor
from istari_service.models import (
    ServiceRequest,
    UserRole,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.organisation_models import RequestRouteSelection
from istari_service.request_participant_models import RequestParticipant


def direct_request_access(actor: Actor) -> ColumnElement[bool]:
    no_request = ActionProjection.request_id.is_(None)
    if actor.role is UserRole.REQUESTER:
        access = exists().where(
            ServiceRequest.id == ActionProjection.request_id,
            ServiceRequest.requester_id == actor.id,
        )
    elif actor.role is UserRole.DELIVERY_SPECIALIST:
        participant = exists().where(
            RequestParticipant.request_id == ActionProjection.request_id,
            RequestParticipant.user_id == actor.id,
            RequestParticipant.ended_at.is_(None),
        )
        access = exists().where(
            ServiceRequest.id == ActionProjection.request_id,
            or_(ServiceRequest.assigned_specialist_id == actor.id, participant),
        )
    else:
        access = exists().where(
            WorkflowTask.request_id == ActionProjection.request_id,
            WorkflowTask.assignee_user_id == actor.id,
            WorkflowTask.candidate_role == actor.role,
            WorkflowTask.status.in_(
                [
                    WorkflowTaskStatus.CLAIM_PENDING,
                    WorkflowTaskStatus.CLAIMED,
                    WorkflowTaskStatus.COMPLETION_PENDING,
                    WorkflowTaskStatus.ERROR,
                ]
            ),
        )
    return or_(no_request, access)


def candidate_access(actor: Actor) -> ColumnElement[bool]:
    platform = (
        and_(
            ActionProjection.organisation_unit_id.is_(None),
            ActionProjection.request_id.is_(None),
        )
        if actor.role is UserRole.PLATFORM_ADMIN
        else false()
    )
    membership = exists().where(
        ActionProjection.organisation_unit_id.in_(actor.organisation_unit_ids),
    )
    routed = or_(
        ActionProjection.request_id.is_(None),
        exists().where(
            RequestRouteSelection.request_id == ActionProjection.request_id,
            RequestRouteSelection.unit_id == ActionProjection.organisation_unit_id,
        ),
    )
    scoped = and_(
        ActionProjection.organisation_unit_id.is_(None),
        ActionProjection.required_scope == actor.scope,
        or_(
            ActionProjection.request_id.is_(None),
            exists().where(
                WorkflowTask.request_id == ActionProjection.request_id,
                WorkflowTask.candidate_role == actor.role,
                WorkflowTask.completed_at.is_(None),
            ),
        ),
    )
    return or_(platform, scoped, and_(membership, routed))
