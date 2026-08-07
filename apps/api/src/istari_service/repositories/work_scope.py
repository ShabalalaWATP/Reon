"""SQL predicates that enforce work ownership before rows are loaded."""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, or_

from istari_service.domain import Actor
from istari_service.models import ServiceRequest, UserRole, WorkflowTaskStatus
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.repositories.organisation import route_membership_condition


def work_scope_conditions(actor: Actor) -> tuple[ColumnElement[bool], ...]:
    conditions: list[ColumnElement[bool]] = [
        StoredWorkflowTask.candidate_role == actor.role,
        ServiceRequest.status == StoredWorkflowTask.expected_status,
        or_(
            and_(
                StoredWorkflowTask.status == WorkflowTaskStatus.OPEN,
                StoredWorkflowTask.assignee_user_id.is_(None),
            ),
            and_(
                StoredWorkflowTask.status.in_(
                    [
                        WorkflowTaskStatus.CLAIM_PENDING,
                        WorkflowTaskStatus.CLAIMED,
                        WorkflowTaskStatus.COMPLETION_PENDING,
                        WorkflowTaskStatus.ERROR,
                    ]
                ),
                StoredWorkflowTask.assignee_user_id == actor.id,
            ),
        ),
    ]
    if actor.role is UserRole.REQUESTER:
        conditions.append(ServiceRequest.requester_id == actor.id)
    elif actor.role is UserRole.DELIVERY_TEAM_LEAD:
        conditions.append(ServiceRequest.assigned_delivery_team == actor.scope)
    elif actor.role is UserRole.DELIVERY_SPECIALIST:
        conditions.append(ServiceRequest.assigned_specialist_id == actor.id)
    membership = route_membership_condition(actor)
    if membership is not None:
        conditions.append(membership)
    return tuple(conditions)
