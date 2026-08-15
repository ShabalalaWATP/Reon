"""Bounded operator recovery for workflow commands that exhausted retries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.repositories.event_store import append_request_event
from mist_service.work_command_types import WorkCommandType
from mist_service.workflow_command_results import (
    RETRY_EXHAUSTED_MESSAGE,
    stored_work_id,
)

RECOVERY_CONFIRMATION = "REQUEUE_FAILED_WORKFLOW"


@dataclass(frozen=True, slots=True)
class WorkflowRecoveryReport:
    request_id: UUID
    failed_commands: int
    requeued_commands: int
    applied: bool


async def recover_failed_workflow(
    session: AsyncSession,
    request_id: UUID,
    *,
    apply: bool = False,
    confirmation: str | None = None,
) -> WorkflowRecoveryReport:
    """Inspect or requeue only failed workflow commands for one known request."""

    if apply and confirmation != RECOVERY_CONFIRMATION:
        raise ValueError("workflow recovery requires the exact confirmation")
    request = await session.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise ValueError("the request does not exist")
    commands = list(
        await session.scalars(
            select(WorkflowOutbox)
            .where(
                WorkflowOutbox.request_id == request_id,
                WorkflowOutbox.status == OutboxStatus.FAILED,
            )
            .with_for_update()
        )
    )
    if not apply or not commands:
        return WorkflowRecoveryReport(request_id, len(commands), 0, False)

    now = datetime.now(UTC)
    requeued = 0
    for command in commands:
        task_status = _recoverable_task_status(command)
        if task_status is False:
            continue
        if isinstance(task_status, WorkflowTaskStatus):
            task_id = stored_work_id(command.payload)
            task = (
                await session.scalar(
                    select(WorkflowTask)
                    .where(WorkflowTask.id == task_id)
                    .with_for_update()
                )
                if task_id is not None
                else None
            )
            if task is None or task.status is not WorkflowTaskStatus.ERROR:
                continue
            task.status = task_status
        command.status = OutboxStatus.PENDING
        command.attempts = 0
        command.available_at = now
        command.last_error = None
        command.lease_owner = None
        requeued += 1
    if requeued == 0:
        return WorkflowRecoveryReport(request_id, len(commands), 0, False)
    instance = await session.scalar(
        select(WorkflowInstance)
        .where(WorkflowInstance.request_id == request_id)
        .with_for_update()
    )
    if instance is not None and instance.status == WorkflowInstanceStatus.ERROR:
        instance.status = (
            WorkflowInstanceStatus.START_PENDING
            if request.status == RequestStatus.ROUTING_PENDING
            else WorkflowInstanceStatus.ACTIVE
        )
        instance.last_error = None
    request.workflow_error = None
    await append_request_event(
        session,
        request_id=request_id,
        actor_id=None,
        event_type="workflow_recovery_queued",
        message="Workflow recovery queued by support.",
        prior_status=request.status,
        next_status=request.status,
    )
    return WorkflowRecoveryReport(request_id, len(commands), requeued, True)


def _recoverable_task_status(
    command: WorkflowOutbox,
) -> WorkflowTaskStatus | bool:
    if (
        command.event_type == "START_PROCESS"
        and command.last_error == "Workflow start is unavailable."
    ):
        return True
    if command.last_error != RETRY_EXHAUSTED_MESSAGE:
        return False
    if command.event_type == WorkCommandType.CLAIM_TASK.value:
        return WorkflowTaskStatus.CLAIM_PENDING
    if command.event_type == WorkCommandType.COMPLETE_TASK.value:
        return WorkflowTaskStatus.COMPLETION_PENDING
    return False
