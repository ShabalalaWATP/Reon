"""Deterministic in-memory implementation of the workflow-engine port."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from mist_service.models import RequestStatus
from mist_service.workflow.errors import (
    UnexpectedWorkflowTask,
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowTaskNotFound,
)
from mist_service.workflow.projection import (
    CUSTOMER_CLARIFICATION_ELEMENT_ID,
    DELIVERY_WORK_ELEMENT_ID,
    INTAKE_REVIEW_ELEMENT_ID,
    REQUESTER_RESPONSE_ELEMENT_ID,
    element_id_for_status,
    status_after_action,
)
from mist_service.workflow.types import (
    ActiveTaskQuery,
    CancelProcessCommand,
    ClaimTaskCommand,
    CompleteTaskCommand,
    ProcessStateQuery,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowProcessSnapshot,
    WorkflowProcessState,
    WorkflowTask,
    WorkflowTaskState,
)


class FakeWorkflowEngine:
    """Run the documented linear/looping process with repeatable opaque keys."""

    def __init__(
        self,
        *,
        visibility_lag_searches: int = 0,
        reachable: bool = True,
    ) -> None:
        if visibility_lag_searches < 0:
            raise ValueError("visibility_lag_searches must not be negative")
        self.reachable = reachable
        self._visibility_lag_searches = visibility_lag_searches
        self._process_counter = 0
        self._task_counter = 0
        self._definition_counter = 0
        self._definitions: dict[tuple[str, int, str | None], str] = {}
        self._started_by_request: dict[
            UUID, tuple[StartProcessCommand, StartedProcess]
        ] = {}
        self._tasks: dict[str, WorkflowTask] = {}
        self._task_by_process: dict[str, str] = {}
        self._status_by_process: dict[str, RequestStatus] = {}
        self._requester_by_process: dict[str, UUID] = {}
        self._specialist_by_process: dict[str, UUID] = {}
        self._visibility_remaining: dict[str, int] = {}
        self._start_commands: list[StartProcessCommand] = []
        self._claim_commands: list[ClaimTaskCommand] = []
        self._completion_commands: list[CompleteTaskCommand] = []
        self._cancellation_commands: list[CancelProcessCommand] = []
        self._terminated_processes: set[str] = set()

    @property
    def start_commands(self) -> tuple[StartProcessCommand, ...]:
        return tuple(self._start_commands)

    @property
    def claim_commands(self) -> tuple[ClaimTaskCommand, ...]:
        return tuple(self._claim_commands)

    @property
    def completion_commands(self) -> tuple[CompleteTaskCommand, ...]:
        return tuple(self._completion_commands)

    @property
    def cancellation_commands(self) -> tuple[CancelProcessCommand, ...]:
        return tuple(self._cancellation_commands)

    @property
    def active_tasks(self) -> tuple[WorkflowTask, ...]:
        return tuple(self._tasks.values())

    async def is_reachable(self) -> bool:
        return self.reachable

    async def start_process(self, command: StartProcessCommand) -> StartedProcess:
        self._require_reachable()
        self._start_commands.append(command)
        previous = self._started_by_request.get(command.request_id)
        if previous is not None:
            previous_command, result = previous
            if previous_command == command:
                return result
            raise WorkflowConflict("start_process", 409)

        version = command.process_definition_version
        resolved_version = 1 if version == -1 else version
        definition_identity = (
            command.process_definition_id,
            resolved_version,
            command.tenant_id,
        )
        definition_key = self._definitions.get(definition_identity)
        if definition_key is None:
            self._definition_counter += 1
            definition_key = f"fake-definition-{self._definition_counter:04d}"
            self._definitions[definition_identity] = definition_key

        self._process_counter += 1
        process_key = f"fake-process-{self._process_counter:04d}"
        result = StartedProcess(
            process_instance_key=process_key,
            process_definition_key=definition_key,
            process_definition_id=command.process_definition_id,
            process_definition_version=resolved_version,
            business_id=str(command.request_id),
        )
        self._started_by_request[command.request_id] = (command, result)
        self._status_by_process[process_key] = RequestStatus.TRIAGE_REVIEW
        self._requester_by_process[process_key] = command.requester_id
        self._create_task(process_key, INTAKE_REVIEW_ELEMENT_ID)
        return result

    async def find_started_process(
        self,
        query: StartedProcessQuery,
    ) -> StartedProcess | None:
        self._require_reachable()
        previous = self._started_by_request.get(query.request_id)
        if previous is None:
            return None
        command, result = previous
        if command.process_definition_id != query.process_definition_id:
            return None
        if (
            query.process_definition_version != -1
            and result.process_definition_version != query.process_definition_version
        ):
            return None
        if command.tenant_id != query.tenant_id:
            return None
        return result

    async def find_process_state(
        self,
        query: ProcessStateQuery,
    ) -> WorkflowProcessSnapshot | None:
        self._require_reachable()
        if query.process_instance_key in self._terminated_processes:
            return WorkflowProcessSnapshot(
                query.process_instance_key, WorkflowProcessState.TERMINATED
            )
        status = self._status_by_process.get(query.process_instance_key)
        if status is None:
            return None
        state = (
            WorkflowProcessState.ACTIVE
            if element_id_for_status(status) is not None
            else WorkflowProcessState.COMPLETED
        )
        return WorkflowProcessSnapshot(query.process_instance_key, state)

    async def search_active_tasks(
        self,
        query: ActiveTaskQuery,
    ) -> tuple[WorkflowTask, ...]:
        self._require_reachable()
        task_key = self._task_by_process.get(query.process_instance_key)
        if task_key is None:
            return ()
        task = self._tasks[task_key]
        if (
            query.expected_element_id is not None
            and task.element_id != query.expected_element_id
        ):
            return ()
        remaining = self._visibility_remaining[task_key]
        if remaining > 0:
            self._visibility_remaining[task_key] = remaining - 1
            return ()
        return (task,)

    async def claim_task(self, command: ClaimTaskCommand) -> None:
        self._require_reachable()
        task = self._tasks.get(command.task_key)
        if task is None:
            raise WorkflowTaskNotFound("claim_task", 404)
        self._claim_commands.append(command)
        assignee = str(command.assignee_id)
        if task.assignee is not None:
            raise WorkflowConflict("claim_task", 409)
        self._tasks[command.task_key] = replace(task, assignee=assignee)

    async def complete_task(self, command: CompleteTaskCommand) -> None:
        self._require_reachable()
        task = self._tasks.get(command.task_key)
        if task is None:
            raise WorkflowTaskNotFound("complete_task", 404)
        if task.process_instance_key != command.process_instance_key:
            raise UnexpectedWorkflowTask("task belongs to another process")
        if task.element_id != command.expected_element_id:
            raise UnexpectedWorkflowTask("task element does not match the command")

        current_status = self._status_by_process[command.process_instance_key]
        next_status = status_after_action(current_status, command.action)
        self._completion_commands.append(command)
        del self._tasks[command.task_key]
        del self._task_by_process[command.process_instance_key]
        del self._visibility_remaining[command.task_key]
        self._status_by_process[command.process_instance_key] = next_status
        if command.specialist_id is not None:
            self._specialist_by_process[command.process_instance_key] = (
                command.specialist_id
            )
        next_element_id = element_id_for_status(next_status)
        if next_element_id is not None:
            self._create_task(command.process_instance_key, next_element_id)

    async def cancel_process(self, command: CancelProcessCommand) -> None:
        self._require_reachable()
        if command.process_instance_key not in self._status_by_process:
            raise WorkflowTaskNotFound("cancel_process", 404)
        self._cancellation_commands.append(command)
        task_key = self._task_by_process.pop(command.process_instance_key, None)
        if task_key is not None:
            self._tasks.pop(task_key, None)
            self._visibility_remaining.pop(task_key, None)
        self._terminated_processes.add(command.process_instance_key)

    def status_for_process(self, process_instance_key: str) -> RequestStatus:
        """Expose deterministic projection state to tests without mutable access."""

        return self._status_by_process[process_instance_key]

    def _create_task(self, process_instance_key: str, element_id: str) -> None:
        self._task_counter += 1
        task_key = f"fake-task-{self._task_counter:04d}"
        assignee_id: UUID | None = None
        if element_id in {
            REQUESTER_RESPONSE_ELEMENT_ID,
            CUSTOMER_CLARIFICATION_ELEMENT_ID,
        }:
            assignee_id = self._requester_by_process[process_instance_key]
        elif element_id == DELIVERY_WORK_ELEMENT_ID:
            assignee_id = self._specialist_by_process.get(process_instance_key)
        self._tasks[task_key] = WorkflowTask(
            task_key=task_key,
            process_instance_key=process_instance_key,
            element_id=element_id,
            state=WorkflowTaskState.CREATED,
            assignee=None if assignee_id is None else str(assignee_id),
        )
        self._task_by_process[process_instance_key] = task_key
        self._visibility_remaining[task_key] = self._visibility_lag_searches

    def _require_reachable(self) -> None:
        if not self.reachable:
            raise WorkflowEngineUnavailable("fake workflow engine is unavailable")
