"""Object-level visibility predicates for stored notifications."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, exists, false, or_

from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationRecipient,
)
from mist_service.domain import Actor
from mist_service.models import ServiceRequest, UserRole, WorkflowTask
from mist_service.organisation_models import RequestRouteSelection
from mist_service.qc_membership import (
    QC_TEAM_ID,
    live_qc_manager_condition,
    live_qc_membership_condition,
)
from mist_service.repositories.request_participants import (
    eligible_participant_condition,
)
from mist_service.repositories.route_access import (
    live_selected_route_membership_condition,
    live_unit_membership_condition,
)
from mist_service.schemas.actions import NotificationFilterState
from mist_service.team_models import WorkspacePosition


def access_condition(actor: Actor) -> ColumnElement[bool]:
    now = datetime.now(UTC)
    account = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ACCOUNT,
        NotificationEvent.request_id.is_(None),
    )
    requester = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.REQUESTER,
        exists().where(
            ServiceRequest.id == NotificationEvent.request_id,
            ServiceRequest.requester_id == actor.id,
        ),
    )
    if actor.role is UserRole.DELIVERY_SPECIALIST:
        assignee_access = eligible_participant_condition(
            NotificationEvent.request_id, actor.id, now
        )
    else:
        assigned_task = exists().where(
            WorkflowTask.request_id == NotificationEvent.request_id,
            WorkflowTask.assignee_user_id == actor.id,
            WorkflowTask.candidate_role == actor.role,
            WorkflowTask.completed_at.is_(None),
        )
        assignee_access = (
            assigned_task
            if actor.role is UserRole.QUALITY_RELEASE
            else and_(
                assigned_task,
                live_selected_route_membership_condition(
                    actor, NotificationEvent.request_id, now
                ),
            )
        )
    assignee = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ASSIGNEE,
        assignee_access,
    )
    qc_team = (
        NotificationRecipient.organisation_unit_id == QC_TEAM_ID
        if actor.role is UserRole.QUALITY_RELEASE
        else false()
    )
    route_member = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ROUTE_MEMBER,
        live_unit_membership_condition(
            actor.id,
            NotificationRecipient.organisation_unit_id,
            now,
        ),
        or_(
            NotificationEvent.request_id.is_(None),
            qc_team,
            exists().where(
                RequestRouteSelection.request_id == NotificationEvent.request_id,
                RequestRouteSelection.unit_id
                == NotificationRecipient.organisation_unit_id,
            ),
        ),
    )
    role_scope = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ROLE_SCOPE,
        NotificationRecipient.required_scope == actor.scope,
        or_(
            NotificationEvent.request_id.is_(None),
            exists().where(
                WorkflowTask.request_id == NotificationEvent.request_id,
                WorkflowTask.candidate_role == actor.role,
                WorkflowTask.completed_at.is_(None),
            ),
        ),
    )
    access = or_(account, requester, assignee, route_member, role_scope)
    if actor.role is UserRole.REQUESTER:
        return access
    conflict_free = or_(
        NotificationEvent.request_id.is_(None),
        exists().where(
            ServiceRequest.id == NotificationEvent.request_id,
            ServiceRequest.requester_id != actor.id,
        ),
    )
    visible = and_(access, conflict_free)
    if actor.role is not UserRole.QUALITY_RELEASE:
        return visible
    return and_(
        visible,
        live_qc_membership_condition(actor.id, now),
        or_(
            NotificationRecipient.required_workspace_position.is_(None),
            and_(
                NotificationRecipient.required_workspace_position
                == WorkspacePosition.MANAGER,
                live_qc_manager_condition(actor.id, now),
            ),
        ),
    )


def state_filter(states: list[NotificationFilterState]) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = []
    if NotificationFilterState.UNREAD in states:
        conditions.append(
            and_(
                NotificationRecipient.read_at.is_(None),
                NotificationRecipient.archived_at.is_(None),
            )
        )
    if NotificationFilterState.READ in states:
        conditions.append(
            and_(
                NotificationRecipient.read_at.is_not(None),
                NotificationRecipient.archived_at.is_(None),
            )
        )
    if NotificationFilterState.ARCHIVED in states:
        conditions.append(NotificationRecipient.archived_at.is_not(None))
    if NotificationFilterState.ACTION_COMPLETED in states:
        conditions.append(NotificationRecipient.action_completed_at.is_not(None))
    return or_(*conditions)
