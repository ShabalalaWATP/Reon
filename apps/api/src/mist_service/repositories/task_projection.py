"""Build product-owned projections of active workflow tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mist_service.models import (
    ServiceRequest,
    WorkflowInstance,
    WorkflowTaskStatus,
)
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.policies import ROLE_BY_STAGE
from mist_service.workflow.types import WorkflowTask


def next_task_projection(
    request: ServiceRequest,
    instance: WorkflowInstance,
    next_task: WorkflowTask,
) -> StoredWorkflowTask:
    assignee_id: UUID | None = None
    if next_task.assignee:
        try:
            assignee_id = UUID(next_task.assignee)
        except ValueError:
            assignee_id = None
    return StoredWorkflowTask(
        request_id=request.id,
        workflow_instance_id=instance.id,
        task_key=next_task.task_key,
        element_id=next_task.element_id,
        name=next_task.element_id.replace("_", " ").title(),
        candidate_role=ROLE_BY_STAGE[request.status],
        expected_status=request.status,
        status=(WorkflowTaskStatus.CLAIMED if assignee_id else WorkflowTaskStatus.OPEN),
        assignee_user_id=assignee_id,
        claimed_at=datetime.now(UTC) if assignee_id else None,
    )
