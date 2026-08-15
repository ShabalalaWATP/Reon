"""Object-level visibility predicates for projected personal actions."""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, exists, false, or_

from mist_service.action_notification_models import ActionProjection
from mist_service.domain import Actor
from mist_service.models import (
    ServiceRequest,
    UserRole,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.organisation_models import RequestRouteSelection
from mist_service.qc_membership import QC_TEAM_ID, live_qc_membership_condition
from mist_service.repositories.request_participants import (
    eligible_participant_condition,
)
from mist_service.repositories.route_access import (
    live_selected_route_membership_condition,
    live_unit_membership_condition,
)


def direct_request_access(actor: Actor) -> ColumnElement[bool]:
    now = datetime.now(UTC)
    no_request = ActionProjection.request_id.is_(None)
    access: ColumnElement[bool]
    if actor.role is UserRole.REQUESTER:
        access = exists().where(
            ServiceRequest.id == ActionProjection.request_id,
            ServiceRequest.requester_id == actor.id,
        )
    elif actor.role is UserRole.DELIVERY_SPECIALIST:
        access = eligible_participant_condition(
            ActionProjection.request_id,
            actor.id,
            now,
        )
    else:
        assigned_task = exists().where(
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
        access = (
            assigned_task
            if actor.role is UserRole.QUALITY_RELEASE
            else and_(
                assigned_task,
                live_selected_route_membership_condition(
                    actor, ActionProjection.request_id, now
                ),
            )
        )
    conflict_free = exists().where(
        ServiceRequest.id == ActionProjection.request_id,
        ServiceRequest.requester_id != actor.id,
    )
    result = or_(
        no_request,
        access if actor.role is UserRole.REQUESTER else and_(access, conflict_free),
    )
    return (
        and_(
            result,
            live_qc_membership_condition(actor.id, now),
        )
        if actor.role is UserRole.QUALITY_RELEASE
        else result
    )


def candidate_access(actor: Actor) -> ColumnElement[bool]:
    now = datetime.now(UTC)
    platform = (
        and_(
            ActionProjection.organisation_unit_id.is_(None),
            ActionProjection.request_id.is_(None),
        )
        if actor.role is UserRole.PLATFORM_ADMIN
        else false()
    )
    membership = live_unit_membership_condition(
        actor.id,
        ActionProjection.organisation_unit_id,
        now,
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
    conflict_free = or_(
        ActionProjection.request_id.is_(None),
        exists().where(
            ServiceRequest.id == ActionProjection.request_id,
            ServiceRequest.requester_id != actor.id,
        ),
    )
    qc_team = (
        and_(
            ActionProjection.organisation_unit_id == QC_TEAM_ID,
            live_qc_membership_condition(actor.id, now),
        )
        if actor.role is UserRole.QUALITY_RELEASE
        else false()
    )
    return and_(
        conflict_free,
        or_(platform, scoped, qc_team, and_(membership, routed)),
    )
