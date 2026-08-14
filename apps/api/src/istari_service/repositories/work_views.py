"""Presentation mapping for persisted work-queue records."""

from uuid import UUID

from istari_service.domain import WorkRecord
from istari_service.models import (
    ServiceRequest,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.policies import allowed_actions
from istari_service.repositories.auth import actor_from_user
from istari_service.repositories.requests import record_from_request
from istari_service.schemas.work import WorkItem
from istari_service.work_types import WorkBundle


def build_work_bundle(
    task: WorkflowTask,
    request: ServiceRequest,
    instance: WorkflowInstance,
    *,
    participant_ids: frozenset[UUID] = frozenset(),
) -> WorkBundle:
    """Map one persisted task and request to the application work bundle."""
    process_key = instance.process_instance_key
    if process_key is None:
        raise ValueError("active work requires a process instance key")
    record = WorkRecord(
        id=task.id,
        request=record_from_request(request, participant_ids),
        engine_task_key=task.task_key,
        process_instance_key=process_key,
        element_id=task.element_id,
        task_status=task.status,
        assignee_id=task.assignee_user_id,
        completed_at=task.completed_at,
    )
    view = WorkItem(
        id=task.id,
        request_id=request.id,
        request_reference=request.reference,
        request_version=request.version,
        title=request.title,
        stage=request.status,
        status=task.status.value,
        assignee_id=task.assignee_user_id,
        assignee_display_name=task.assignee.display_name if task.assignee else None,
        delivery_team=request.assigned_delivery_team,
        available_actions=list(allowed_actions(actor_from_user(task.assignee), request))
        if (
            task.assignee
            and task.status is WorkflowTaskStatus.CLAIMED
            and request.assigned_delivery_team_id is None
        )
        else [],
        assigned_to_current_user=False,
        assignment_role=None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    return WorkBundle(record, view)
