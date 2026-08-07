"""Final database-scoped request lookup for authorised detail reads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.repositories.organisation import (
    has_route_membership,
    route_membership_condition,
)


async def scoped_request(
    session: AsyncSession,
    request_id: UUID,
    actor: Actor,
    *,
    lock: bool,
) -> ServiceRequest | None:
    if lock and not await _current_actor_is_valid(session, actor):
        return None
    query = select(ServiceRequest).where(ServiceRequest.id == request_id)
    if actor.role is UserRole.REQUESTER:
        query = query.where(ServiceRequest.requester_id == actor.id)
    else:
        waiting = await _waiting_clarification_request(
            session,
            request_id,
            actor,
            lock=lock,
        )
        if waiting is not None:
            return waiting
        query = _active_work_query(query, actor)
    if lock:
        query = query.with_for_update()
    request = await session.scalar(query)
    if (
        request is not None
        and lock
        and actor.role is not UserRole.REQUESTER
        and not await has_route_membership(session, actor, request_id, lock=True)
    ):
        return None
    return request


async def _current_actor_is_valid(session: AsyncSession, actor: Actor) -> bool:
    current_user = await session.scalar(
        select(User).where(User.id == actor.id).with_for_update()
    )
    return bool(
        current_user is not None
        and current_user.is_active
        and current_user.role is actor.role
        and current_user.scope == actor.scope
    )


async def _waiting_clarification_request(
    session: AsyncSession,
    request_id: UUID,
    actor: Actor,
    *,
    lock: bool,
) -> ServiceRequest | None:
    if actor.role not in {
        UserRole.DELIVERY_TEAM_LEAD,
        UserRole.DELIVERY_SPECIALIST,
    }:
        return None
    query = (
        select(ServiceRequest)
        .join(WorkflowInstance, WorkflowInstance.request_id == ServiceRequest.id)
        .where(
            ServiceRequest.id == request_id,
            ServiceRequest.status == RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            WorkflowInstance.status == WorkflowInstanceStatus.ACTIVE,
            WorkflowInstance.process_instance_key.is_not(None),
        )
    )
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        query = query.where(ServiceRequest.assigned_delivery_team == actor.scope)
    else:
        query = query.where(ServiceRequest.assigned_specialist_id == actor.id)
    membership = route_membership_condition(actor)
    if membership is not None:
        query = query.where(membership)
    if lock:
        query = query.with_for_update()
    request = await session.scalar(query)
    if request is None:
        return None
    if lock and not await has_route_membership(session, actor, request_id, lock=True):
        return None
    return request


def _active_work_query(
    query: Select[tuple[ServiceRequest]],
    actor: Actor,
) -> Select[tuple[ServiceRequest]]:
    query = (
        query.join(
            StoredWorkflowTask,
            StoredWorkflowTask.request_id == ServiceRequest.id,
        )
        .join(
            WorkflowInstance,
            WorkflowInstance.id == StoredWorkflowTask.workflow_instance_id,
        )
        .where(
            StoredWorkflowTask.assignee_user_id == actor.id,
            StoredWorkflowTask.candidate_role == actor.role,
            StoredWorkflowTask.expected_status == ServiceRequest.status,
            StoredWorkflowTask.completed_at.is_(None),
            StoredWorkflowTask.status.in_(
                [
                    WorkflowTaskStatus.CLAIM_PENDING,
                    WorkflowTaskStatus.CLAIMED,
                    WorkflowTaskStatus.COMPLETION_PENDING,
                    WorkflowTaskStatus.ERROR,
                ]
            ),
            WorkflowInstance.request_id == ServiceRequest.id,
            WorkflowInstance.status == WorkflowInstanceStatus.ACTIVE,
            WorkflowInstance.current_element_id == StoredWorkflowTask.element_id,
            WorkflowInstance.process_instance_key.is_not(None),
        )
    )
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        query = query.where(ServiceRequest.assigned_delivery_team == actor.scope)
    elif actor.role is UserRole.DELIVERY_SPECIALIST:
        query = query.where(ServiceRequest.assigned_specialist_id == actor.id)
    membership = route_membership_condition(actor)
    return query.where(membership) if membership is not None else query
