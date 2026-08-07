"""Final-boundary validation and engine command construction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import (
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowTaskStatus,
)
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.policies import can_access_work, may_complete
from istari_service.repositories.auth import actor_from_user_with_memberships
from istari_service.repositories.organisation import (
    has_route_membership,
    resolve_routing_selection,
)
from istari_service.repositories.requests import record_from_request
from istari_service.repositories.work_actions import validate_work_effect
from istari_service.schemas.work import AssignSpecialist
from istari_service.work_command_types import PendingWorkCommand, WorkCommandType
from istari_service.workflow.types import (
    CompleteTaskCommand,
    WorkflowAction,
    WorkflowRouteSelection,
)


async def validated_command_state(
    session: AsyncSession,
    command: PendingWorkCommand,
    request_id: UUID,
    *,
    managed_products_enabled: bool = False,
) -> tuple[Actor, WorkRecord]:
    """Lock and reauthorise the exact actor, object, version and assignment."""

    task = await session.scalar(
        select(StoredWorkflowTask)
        .where(StoredWorkflowTask.id == command.work_id)
        .with_for_update()
    )
    request = await session.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id).with_for_update()
    )
    user = await session.scalar(
        select(User).where(User.id == command.actor_id).with_for_update()
    )
    instance = await session.scalar(
        select(WorkflowInstance)
        .where(WorkflowInstance.request_id == request_id)
        .with_for_update()
    )
    expected_task_status = (
        WorkflowTaskStatus.CLAIM_PENDING
        if command.command_type is WorkCommandType.CLAIM_TASK
        else WorkflowTaskStatus.COMPLETION_PENDING
    )
    if (
        task is None
        or request is None
        or user is None
        or instance is None
        or not user.is_active
        or task.task_key != command.task_key
        or task.element_id != command.element_id
        or task.status is not expected_task_status
        or task.assignee_user_id != user.id
        or task.candidate_role is not user.role
        or task.expected_status is not request.status
        or request.status is not command.request_status
        or request.version != command.request_version
        or instance.process_instance_key != command.process_instance_key
    ):
        raise InvalidAction()
    actor = await actor_from_user_with_memberships(session, user)
    if not can_access_work(actor, request) or not await has_route_membership(
        session, actor, request.id, lock=True
    ):
        raise InvalidAction()
    work = WorkRecord(
        id=task.id,
        request=record_from_request(request),
        engine_task_key=task.task_key,
        process_instance_key=command.process_instance_key,
        element_id=task.element_id,
        task_status=task.status,
        assignee_id=task.assignee_user_id,
        completed_at=task.completed_at,
    )
    if command.completion is not None:
        action = WorkflowAction(command.completion.action)
        if not may_complete(actor, request, action.value, task.assignee_user_id):
            raise InvalidAction()
        await _validate_assignment(session, request, command)
        resolved_routing = await resolve_routing_selection(
            session,
            request,
            command.completion,
            lock=True,
        )
        if resolved_routing != command.routing:
            raise InvalidAction()
        await validate_work_effect(
            session,
            request,
            actor,
            command.completion,
            managed_products_enabled=managed_products_enabled,
        )
    return actor, work


async def _validate_assignment(
    session: AsyncSession,
    request: ServiceRequest,
    command: PendingWorkCommand,
) -> None:
    payload = command.completion
    if not isinstance(payload, AssignSpecialist):
        return
    specialist = await session.get(User, payload.specialist_id)
    specialist_actor = (
        await actor_from_user_with_memberships(session, specialist)
        if specialist is not None
        else None
    )
    if (
        specialist is None
        or not specialist.is_active
        or specialist.role is not UserRole.DELIVERY_SPECIALIST
        or (
            request.assigned_delivery_team_id is None
            and specialist.scope != request.assigned_delivery_team
        )
        or specialist_actor is None
        or not await has_route_membership(
            session, specialist_actor, request.id, lock=True
        )
    ):
        raise InvalidAction()


def completion_engine_command(command: PendingWorkCommand) -> CompleteTaskCommand:
    payload = command.completion
    if payload is None:
        raise InvalidAction()
    return CompleteTaskCommand(
        task_key=command.task_key,
        process_instance_key=command.process_instance_key,
        expected_element_id=command.element_id,
        action=WorkflowAction(payload.action),
        specialist_id=(
            payload.specialist_id if isinstance(payload, AssignSpecialist) else None
        ),
        route_selection=(
            WorkflowRouteSelection(
                unit_id=command.routing.unit_id,
                unit_code=command.routing.unit_code,
                candidate_groups=command.routing.candidate_groups,
            )
            if command.routing is not None
            else None
        ),
    )
