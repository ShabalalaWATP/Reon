"""Atomic local projection after a proven workflow claim."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor, WorkRecord
from mist_service.models import ServiceRequest, WorkflowTaskStatus
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.repositories.event_store import append_request_event


async def project_claim(
    session: AsyncSession,
    work: WorkRecord,
    actor: Actor,
) -> bool:
    result = await session.execute(
        update(StoredWorkflowTask)
        .where(
            StoredWorkflowTask.id == work.id,
            StoredWorkflowTask.status == WorkflowTaskStatus.CLAIM_PENDING,
            StoredWorkflowTask.assignee_user_id == actor.id,
        )
        .values(
            status=WorkflowTaskStatus.CLAIMED,
            claimed_at=datetime.now(UTC),
        )
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return False
    request = await session.get(ServiceRequest, work.request.id)
    if request is None:
        return False
    request.workflow_error = None
    await append_request_event(
        session,
        request_id=request.id,
        actor_id=actor.id,
        event_type="workflow_claimed",
        message="Work item claimed.",
        prior_status=request.status,
        next_status=request.status,
        details={"taskKey": work.engine_task_key},
    )
    await session.flush()
    return True
