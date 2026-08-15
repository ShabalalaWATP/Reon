"""Atomic product projections for workflow-command outcomes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import WorkRecord
from mist_service.models import (
    OutboxStatus,
    ServiceRequest,
    User,
    WorkflowOutbox,
    WorkflowTaskStatus,
)
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.policies import can_access_work
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.route_access import has_route_membership
from mist_service.workflow.types import WorkflowTask
from mist_service.workflow_lease_fencing import retry_delay_seconds

SUPPORT_MESSAGE = "A recorded workflow action needs support."
RETRY_MESSAGE = "A workflow action is recorded and will be retried."
RETRY_EXHAUSTED_MESSAGE = "Workflow retries are exhausted; support may requeue it."


async def schedule_retry(
    session: AsyncSession,
    outbox: WorkflowOutbox,
    work_id: UUID,
    *,
    max_attempts: int,
) -> None:
    exhausted = outbox.attempts >= max_attempts
    outbox.status = OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING
    outbox.lease_owner = None
    outbox.available_at = datetime.now(UTC) + timedelta(
        seconds=retry_delay_seconds(outbox.attempts)
    )
    outbox.last_error = RETRY_EXHAUSTED_MESSAGE if exhausted else RETRY_MESSAGE
    request = await session.get(ServiceRequest, outbox.request_id)
    task = await session.get(StoredWorkflowTask, work_id)
    if request is not None:
        request.workflow_error = SUPPORT_MESSAGE if exhausted else RETRY_MESSAGE
    if exhausted and task is not None:
        task.status = WorkflowTaskStatus.ERROR


async def mark_support_failure(
    session: AsyncSession,
    outbox: WorkflowOutbox,
    work_id: UUID | None,
) -> None:
    outbox.status = OutboxStatus.FAILED
    outbox.lease_owner = None
    outbox.last_error = SUPPORT_MESSAGE
    request = await session.get(ServiceRequest, outbox.request_id)
    if request is not None:
        request.workflow_error = SUPPORT_MESSAGE
    if work_id is not None:
        task = await session.get(StoredWorkflowTask, work_id)
        if task is not None:
            task.status = WorkflowTaskStatus.ERROR


def mark_sent(outbox: WorkflowOutbox) -> None:
    outbox.status = OutboxStatus.SENT
    outbox.lease_owner = None
    outbox.sent_at = datetime.now(UTC)
    outbox.last_error = None


async def project_competing_claim(
    session: AsyncSession,
    outbox: WorkflowOutbox,
    work: WorkRecord,
    engine_task: WorkflowTask,
) -> bool:
    """Project a proven competing assignee without reopening the engine task."""

    try:
        assignee_id = UUID(engine_task.assignee or "")
    except ValueError:
        await mark_support_failure(session, outbox, work.id)
        return False
    user = await session.scalar(
        select(User).where(User.id == assignee_id).with_for_update()
    )
    task = await session.get(StoredWorkflowTask, work.id)
    request = await session.get(ServiceRequest, work.request.id)
    actor = (
        await actor_from_user_with_memberships(session, user)
        if user is not None
        else None
    )
    pool_verified = (
        actor is not None
        and request is not None
        and await has_route_membership(session, actor, request.id, lock=True)
    )
    if (
        user is None
        or task is None
        or request is None
        or not user.is_active
        or user.role is not task.candidate_role
        or actor is None
        or not can_access_work(actor, request, pool_membership_verified=pool_verified)
    ):
        await mark_support_failure(session, outbox, work.id)
        return False
    task.status = WorkflowTaskStatus.CLAIMED
    task.assignee_user_id = user.id
    task.claimed_at = datetime.now(UTC)
    request.workflow_error = None
    outbox.status = OutboxStatus.FAILED
    outbox.lease_owner = None
    outbox.last_error = "The engine task was claimed by another user."
    await append_request_event(
        session,
        request_id=request.id,
        actor_id=user.id,
        event_type="workflow_claimed",
        message="Work item claim reconciled.",
        prior_status=request.status,
        next_status=request.status,
        details={"taskKey": task.task_key},
    )
    return True


def stored_work_id(payload: dict[str, object]) -> UUID | None:
    try:
        return UUID(str(payload["workId"]))
    except (KeyError, ValueError):
        return None
