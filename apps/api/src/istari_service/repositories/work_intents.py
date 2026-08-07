"""Transactional persistence of human-action workflow intents."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import (
    OutboxStatus,
    ServiceRequest,
    WorkflowOutbox,
    WorkflowTaskStatus,
)
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.policies import can_access_work, may_complete
from istari_service.repositories.organisation import (
    has_route_membership,
    resolve_routing_selection,
)
from istari_service.repositories.work_actions import validate_work_effect
from istari_service.schemas.work import CompletionPayload
from istari_service.work_command_types import (
    RoutingSelection,
    WorkCommandType,
    command_payload,
)
from istari_service.workflow.types import WorkflowAction

PENDING_MESSAGE = "A workflow action is recorded and awaiting processing."


async def prepare_claim_intent(
    session: AsyncSession,
    work: WorkRecord,
    actor: Actor,
) -> UUID:
    task, request = await _locked_state(session, work)
    if (
        task.status is not WorkflowTaskStatus.OPEN
        or task.assignee_user_id is not None
        or task.candidate_role is not actor.role
        or not can_access_work(actor, request)
        or not await has_route_membership(session, actor, request.id)
    ):
        raise InvalidAction()
    task.status = WorkflowTaskStatus.CLAIM_PENDING
    task.assignee_user_id = actor.id
    request.workflow_error = PENDING_MESSAGE
    outbox = _outbox(
        work,
        actor,
        WorkCommandType.CLAIM_TASK,
        completion=None,
    )
    session.add(outbox)
    await session.flush()
    return outbox.id


async def prepare_completion_intent(
    session: AsyncSession,
    work: WorkRecord,
    actor: Actor,
    payload: CompletionPayload,
    *,
    managed_products_enabled: bool = False,
) -> UUID:
    task, request = await _locked_state(session, work)
    action = WorkflowAction(payload.action)
    if (
        task.status is not WorkflowTaskStatus.CLAIMED
        or task.assignee_user_id != actor.id
        or not may_complete(actor, request, action.value, task.assignee_user_id)
        or not await has_route_membership(session, actor, request.id)
    ):
        raise InvalidAction()
    await validate_work_effect(
        session,
        request,
        actor,
        payload,
        managed_products_enabled=managed_products_enabled,
    )
    routing = await resolve_routing_selection(
        session,
        request,
        payload,
        lock=True,
    )
    task.status = WorkflowTaskStatus.COMPLETION_PENDING
    request.workflow_error = PENDING_MESSAGE
    outbox = _outbox(
        work,
        actor,
        WorkCommandType.COMPLETE_TASK,
        completion=payload,
        routing=routing,
    )
    session.add(outbox)
    await session.flush()
    return outbox.id


async def _locked_state(
    session: AsyncSession,
    work: WorkRecord,
) -> tuple[StoredWorkflowTask, ServiceRequest]:
    task = await session.scalar(
        select(StoredWorkflowTask)
        .where(StoredWorkflowTask.id == work.id)
        .with_for_update()
    )
    request = await session.scalar(
        select(ServiceRequest)
        .where(ServiceRequest.id == work.request.id)
        .with_for_update()
    )
    if (
        task is None
        or request is None
        or task.task_key != work.engine_task_key
        or task.element_id != work.element_id
        or request.status is not work.request.status
        or request.version != work.request.version
        or task.expected_status is not request.status
    ):
        raise InvalidAction()
    return task, request


def _outbox(
    work: WorkRecord,
    actor: Actor,
    command_type: WorkCommandType,
    *,
    completion: CompletionPayload | None,
    routing: RoutingSelection | None = None,
) -> WorkflowOutbox:
    return WorkflowOutbox(
        request_id=work.request.id,
        event_type=command_type.value,
        payload=command_payload(
            work_id=work.id,
            task_key=work.engine_task_key or "",
            process_instance_key=work.process_instance_key,
            element_id=work.element_id,
            actor_id=actor.id,
            request_version=work.request.version,
            request_status=work.request.status,
            completion=completion,
            routing=routing,
        ),
        idempotency_key=f"{command_type.value.lower()}:{work.engine_task_key}",
        status=OutboxStatus.PENDING,
        available_at=datetime.now(UTC),
    )
