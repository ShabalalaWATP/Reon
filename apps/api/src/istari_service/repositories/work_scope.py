"""SQL predicates that enforce work ownership before rows are loaded."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.orm import aliased

from istari_service.domain import Actor
from istari_service.models import (
    Deliverable,
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowTaskStatus,
)
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.product_models import ProductPackage
from istari_service.qc_membership import live_qc_membership_condition
from istari_service.repositories.route_access import route_membership_condition
from istari_service.request_participant_models import RequestParticipant


def work_scope_conditions(actor: Actor) -> tuple[ColumnElement[bool], ...]:
    assigned_to_actor = StoredWorkflowTask.assignee_user_id == actor.id
    if actor.role is UserRole.DELIVERY_SPECIALIST:
        assigned_to_actor = or_(
            assigned_to_actor,
            exists().where(
                RequestParticipant.request_id == ServiceRequest.id,
                RequestParticipant.user_id == actor.id,
                RequestParticipant.ended_at.is_(None),
            ),
        )
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
                assigned_to_actor,
            ),
        ),
    ]
    if actor.role is UserRole.REQUESTER:
        conditions.append(ServiceRequest.requester_id == actor.id)
    else:
        conditions.append(ServiceRequest.requester_id != actor.id)
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        conditions.append(
            or_(
                ServiceRequest.assigned_delivery_team_id.is_not(None),
                ServiceRequest.assigned_delivery_team == actor.scope,
            )
        )
    elif actor.role is UserRole.DELIVERY_SPECIALIST:
        conditions.append(
            or_(
                ServiceRequest.assigned_specialist_id == actor.id,
                exists().where(
                    RequestParticipant.request_id == ServiceRequest.id,
                    RequestParticipant.user_id == actor.id,
                    RequestParticipant.ended_at.is_(None),
                ),
            )
        )
    elif actor.role is UserRole.QUALITY_RELEASE:
        conditions.extend(_quality_separation_conditions(actor))
        conditions.append(live_qc_membership_condition(actor.id, datetime.now(UTC)))
    membership = route_membership_condition(actor)
    if membership is not None:
        conditions.append(membership)
    return tuple(conditions)


def _quality_separation_conditions(actor: Actor) -> tuple[ColumnElement[bool], ...]:
    latest_package_id = (
        select(ProductPackage.id)
        .where(ProductPackage.request_id == ServiceRequest.id)
        .order_by(ProductPackage.package_version.desc())
        .limit(1)
        .correlate(ServiceRequest)
        .scalar_subquery()
    )
    latest_deliverable_id = (
        select(Deliverable.id)
        .where(Deliverable.request_id == ServiceRequest.id)
        .order_by(Deliverable.version.desc())
        .limit(1)
        .correlate(ServiceRequest)
        .scalar_subquery()
    )
    product_independence = ~exists().where(
        ProductPackage.id == latest_package_id,
        or_(
            ProductPackage.author_user_id == actor.id,
            ProductPackage.manager_approved_by_user_id == actor.id,
        ),
    )
    legacy_author_independence = ~exists().where(
        Deliverable.id == latest_deliverable_id,
        or_(
            Deliverable.author_user_id == actor.id,
            Deliverable.approved_by_user_id == actor.id,
        ),
    )
    release_reviewer_independence = or_(
        ServiceRequest.status != RequestStatus.READY_FOR_RELEASE,
        _not_latest_completed_actor(actor, "quality_review"),
    )
    return (
        product_independence,
        legacy_author_independence,
        _not_latest_completed_actor(actor, "lead_review"),
        release_reviewer_independence,
    )


def _not_latest_completed_actor(actor: Actor, element_id: str) -> ColumnElement[bool]:
    task = aliased(StoredWorkflowTask)
    latest_task_id = (
        select(task.id)
        .where(
            task.request_id == ServiceRequest.id,
            task.element_id == element_id,
            task.status == WorkflowTaskStatus.COMPLETED,
        )
        .order_by(task.completed_at.desc(), task.id.desc())
        .limit(1)
        .correlate(ServiceRequest)
        .scalar_subquery()
    )
    decision = aliased(StoredWorkflowTask)
    return ~exists().where(
        decision.id == latest_task_id,
        decision.assignee_user_id == actor.id,
    )
