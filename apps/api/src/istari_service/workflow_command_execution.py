"""Database-free execution and proof of one leased human workflow command."""

from __future__ import annotations

from dataclasses import dataclass

from istari_service.domain import Actor
from istari_service.work_command_types import PendingWorkCommand, WorkCommandType
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowError,
    WorkflowTaskNotFound,
    WorkflowTaskNotVisible,
)
from istari_service.workflow.lookup import TaskLookupPolicy, wait_for_active_task
from istari_service.workflow.projection import (
    element_id_for_status,
    status_after_action,
)
from istari_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    ProcessStateQuery,
    WorkflowAction,
    WorkflowProcessState,
    WorkflowTask,
)
from istari_service.workflow_command_state import completion_engine_command


@dataclass(frozen=True, slots=True)
class ClaimSucceeded:
    recovered: bool = False


@dataclass(frozen=True, slots=True)
class CompetingClaim:
    task: WorkflowTask
    error: WorkflowError


@dataclass(frozen=True, slots=True)
class CompletionSucceeded:
    next_task: WorkflowTask | None
    reconciliation_needed: bool


@dataclass(frozen=True, slots=True)
class CommandRetry:
    error: WorkflowError


CommandOutcome = ClaimSucceeded | CompetingClaim | CompletionSucceeded | CommandRetry


class WorkflowCommandExecutor:
    def __init__(
        self,
        engine: WorkflowEngine,
        lookup_policy: TaskLookupPolicy,
    ) -> None:
        self._engine = engine
        self._lookup_policy = lookup_policy

    async def execute(
        self,
        command: PendingWorkCommand,
        actor: Actor,
    ) -> CommandOutcome:
        if command.command_type is WorkCommandType.CLAIM_TASK:
            return await self._claim(command, actor)
        return await self._complete(command)

    async def _claim(
        self,
        command: PendingWorkCommand,
        actor: Actor,
    ) -> CommandOutcome:
        try:
            await self._engine.claim_task(ClaimTaskCommand(command.task_key, actor.id))
            return ClaimSucceeded()
        except (WorkflowConflict, WorkflowTaskNotFound) as conflict:
            try:
                task = await wait_for_active_task(
                    self._engine,
                    ActiveTaskQuery(
                        command.process_instance_key,
                        command.element_id,
                    ),
                    policy=self._lookup_policy,
                )
            except WorkflowError as error:
                return CommandRetry(error)
            if task.task_key != command.task_key or task.assignee is None:
                return CommandRetry(conflict)
            if task.assignee == str(command.actor_id):
                return ClaimSucceeded(recovered=True)
            return CompetingClaim(task, conflict)
        except WorkflowError as error:
            return CommandRetry(error)

    async def _complete(
        self,
        command: PendingWorkCommand,
    ) -> CommandOutcome:
        payload = command.completion
        if payload is None:
            raise ValueError("completion payload is required")
        next_status = status_after_action(
            command.request_status,
            WorkflowAction(payload.action),
        )
        expected_element = element_id_for_status(next_status)
        recovered = False
        try:
            await self._engine.complete_task(completion_engine_command(command))
        except (WorkflowConflict, WorkflowTaskNotFound):
            recovered = True
        except WorkflowError as error:
            return CommandRetry(error)
        try:
            next_task = await self._completion_proof(
                command,
                expected_element,
                recovered,
            )
        except WorkflowError as error:
            return CommandRetry(error)
        return CompletionSucceeded(
            next_task=next_task,
            reconciliation_needed=expected_element is not None and next_task is None,
        )

    async def _completion_proof(
        self,
        command: PendingWorkCommand,
        expected_element: str | None,
        recovered: bool,
    ) -> WorkflowTask | None:
        if expected_element is not None:
            try:
                return await wait_for_active_task(
                    self._engine,
                    ActiveTaskQuery(command.process_instance_key, expected_element),
                    policy=self._lookup_policy,
                )
            except WorkflowTaskNotVisible:
                if not recovered:
                    return None
                raise
        if not recovered:
            return None
        process = await self._engine.find_process_state(
            ProcessStateQuery(command.process_instance_key)
        )
        if process is None or process.state != WorkflowProcessState.COMPLETED:
            raise WorkflowTaskNotVisible("terminal process state is not proven")
        return None
