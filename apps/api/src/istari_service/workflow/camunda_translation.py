"""Validate and translate Camunda SDK results into application records."""

from __future__ import annotations

from camunda_orchestration_sdk.models import ProcessInstanceResult, UserTaskResult

from istari_service.workflow.errors import WorkflowContractError
from istari_service.workflow.types import (
    StartedProcess,
    StartedProcessQuery,
    WorkflowTask,
    WorkflowTaskState,
)


def map_task(task: UserTaskResult) -> WorkflowTask:
    """Map a validated Camunda user-task result."""

    try:
        state = WorkflowTaskState(task.state.value)
    except ValueError as exc:
        raise WorkflowContractError(
            "Camunda returned an invalid user-task result"
        ) from exc
    return WorkflowTask(
        task_key=str(task.user_task_key),
        process_instance_key=str(task.process_instance_key),
        element_id=str(task.element_id),
        state=state,
        assignee=task.assignee,
    )


def map_process(
    process: ProcessInstanceResult,
    query: StartedProcessQuery,
) -> StartedProcess:
    """Map a root process only when every immutable identity field matches."""

    business_id = None if process.business_id is None else str(process.business_id)
    if business_id != str(query.request_id):
        raise WorkflowContractError(
            "Camunda returned a process with a different business ID"
        )
    if str(process.process_definition_id) != query.process_definition_id:
        raise WorkflowContractError(
            "Camunda returned a process for a different definition"
        )
    if (
        query.process_definition_version != -1
        and process.process_definition_version != query.process_definition_version
    ):
        raise WorkflowContractError(
            "Camunda returned a process for a different definition version"
        )
    if query.tenant_id is not None and str(process.tenant_id) != query.tenant_id:
        raise WorkflowContractError("Camunda returned a process for a different tenant")
    if process.parent_process_instance_key is not None:
        raise WorkflowContractError(
            "Camunda returned a child process for a root start recovery"
        )
    return StartedProcess(
        process_instance_key=str(process.process_instance_key),
        process_definition_key=str(process.process_definition_key),
        process_definition_id=str(process.process_definition_id),
        process_definition_version=process.process_definition_version,
        business_id=business_id,
    )
