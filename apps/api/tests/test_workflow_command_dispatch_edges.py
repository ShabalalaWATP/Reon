"""Database-free workflow command execution and recovery edges."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import istari_service.workflow_command_execution as execution_module
from istari_service.domain import Actor
from istari_service.models import RequestStatus, UserRole
from istari_service.schemas.work import (
    CloseRequest,
    ProgressRequest,
    ReleaseDeliverable,
)
from istari_service.work_command_types import PendingWorkCommand, WorkCommandType
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowTaskNotFound,
    WorkflowTaskNotVisible,
)
from istari_service.workflow.lookup import TaskLookupPolicy
from istari_service.workflow.types import (
    WorkflowProcessSnapshot,
    WorkflowProcessState,
    WorkflowTask,
    WorkflowTaskState,
)
from istari_service.workflow_command_execution import (
    ClaimSucceeded,
    CommandRetry,
    CompetingClaim,
    CompletionSucceeded,
    WorkflowCommandExecutor,
)


def _state(
    command_type: WorkCommandType = WorkCommandType.CLAIM_TASK,
) -> tuple[Actor, PendingWorkCommand]:
    actor = Actor(
        id=uuid4(),
        username="triage@example.test",
        display_name="Synthetic Triage",
        role=UserRole.INTAKE_TRIAGE,
        scope="Shared queue",
    )
    completion = (
        None
        if command_type is WorkCommandType.CLAIM_TASK
        else CloseRequest(action="close", reason="Synthetic closure reason")
    )
    command = PendingWorkCommand(
        outbox_id=uuid4(),
        command_type=command_type,
        work_id=uuid4(),
        task_key="task-1",
        process_instance_key="process-1",
        element_id="triage-review",
        actor_id=actor.id,
        request_version=1,
        request_status=RequestStatus.TRIAGE_REVIEW,
        attempts=1,
        completion=completion,
    )
    return actor, command


def _executor(engine: object) -> WorkflowCommandExecutor:
    return WorkflowCommandExecutor(
        cast(WorkflowEngine, engine),
        TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            maximum_delay_seconds=0,
        ),
    )


async def test_claim_success_and_engine_outage() -> None:
    actor, command = _state()
    success = await _executor(
        SimpleNamespace(claim_task=AsyncMock(return_value=None))
    ).execute(command, actor)
    assert success == ClaimSucceeded()

    outage = WorkflowEngineUnavailable("synthetic outage")
    retry = await _executor(
        SimpleNamespace(claim_task=AsyncMock(side_effect=outage))
    ).execute(command, actor)
    assert retry == CommandRetry(outage)


@pytest.mark.parametrize("mode", ["same", "unassigned", "competing", "invisible"])
async def test_claim_conflict_recovery(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    actor, command = _state()
    conflict = WorkflowConflict("claim_task", 409)

    async def lookup(*_args: object, **_kwargs: object) -> WorkflowTask:
        if mode == "invisible":
            raise WorkflowTaskNotVisible("not visible")
        assignee = {
            "same": str(actor.id),
            "unassigned": None,
            "competing": str(uuid4()),
        }[mode]
        return WorkflowTask(
            task_key=command.task_key,
            process_instance_key=command.process_instance_key,
            element_id=command.element_id,
            state=WorkflowTaskState.CREATED,
            assignee=assignee,
        )

    monkeypatch.setattr(execution_module, "wait_for_active_task", lookup)
    outcome = await _executor(
        SimpleNamespace(claim_task=AsyncMock(side_effect=conflict))
    ).execute(command, actor)
    if mode == "same":
        assert outcome == ClaimSucceeded(recovered=True)
    elif mode == "competing":
        assert isinstance(outcome, CompetingClaim)
    else:
        assert isinstance(outcome, CommandRetry)


async def test_claim_not_found_uses_the_same_recovery_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, command = _state()
    task = WorkflowTask(
        task_key=command.task_key,
        process_instance_key=command.process_instance_key,
        element_id=command.element_id,
        state=WorkflowTaskState.CREATED,
        assignee=str(actor.id),
    )
    monkeypatch.setattr(
        execution_module,
        "wait_for_active_task",
        AsyncMock(return_value=task),
    )
    outcome = await _executor(
        SimpleNamespace(
            claim_task=AsyncMock(side_effect=WorkflowTaskNotFound("claim_task", 404))
        )
    ).execute(command, actor)
    assert outcome == ClaimSucceeded(recovered=True)


async def test_completion_success_outage_and_recovered_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, command = _state(WorkCommandType.COMPLETE_TASK)
    command = replace(
        command,
        completion=ProgressRequest(
            action="progress",
            priority="MEDIUM",
            destination_unit_id=uuid4(),
        ),
    )
    monkeypatch.setattr(
        execution_module,
        "wait_for_active_task",
        AsyncMock(return_value=None),
    )
    success = await _executor(
        SimpleNamespace(complete_task=AsyncMock(return_value=None))
    ).execute(command, actor)
    assert success == CompletionSucceeded(None, reconciliation_needed=True)

    outage = WorkflowEngineUnavailable("synthetic outage")
    retry = await _executor(
        SimpleNamespace(complete_task=AsyncMock(side_effect=outage))
    ).execute(command, actor)
    assert retry == CommandRetry(outage)

    invisible = WorkflowTaskNotVisible("not proven")
    monkeypatch.setattr(
        execution_module,
        "wait_for_active_task",
        AsyncMock(side_effect=invisible),
    )
    recovered = await _executor(
        SimpleNamespace(
            complete_task=AsyncMock(side_effect=WorkflowConflict("complete_task", 409))
        )
    ).execute(command, actor)
    assert recovered == CommandRetry(invisible)


async def test_terminal_completion_recovery_is_fail_closed() -> None:
    actor, command = _state(WorkCommandType.COMPLETE_TASK)
    command = replace(
        command,
        request_status=RequestStatus.READY_FOR_RELEASE,
        completion=ReleaseDeliverable(
            action="release",
            recipients=["customer@example.test"],
        ),
    )
    for state in (WorkflowProcessState.ACTIVE, WorkflowProcessState.TERMINATED):
        engine = SimpleNamespace(
            complete_task=AsyncMock(
                side_effect=WorkflowTaskNotFound("complete_task", 404)
            ),
            find_process_state=AsyncMock(
                return_value=WorkflowProcessSnapshot("process-1", state)
            ),
        )
        outcome = await _executor(engine).execute(command, actor)
        assert isinstance(outcome, CommandRetry)

    completed = SimpleNamespace(
        complete_task=AsyncMock(side_effect=WorkflowTaskNotFound("complete_task", 404)),
        find_process_state=AsyncMock(
            return_value=WorkflowProcessSnapshot(
                "process-1", WorkflowProcessState.COMPLETED
            )
        ),
    )
    assert await _executor(completed).execute(command, actor) == CompletionSucceeded(
        None,
        reconciliation_needed=False,
    )


async def test_complete_rejects_missing_stored_payload() -> None:
    actor, command = _state(WorkCommandType.COMPLETE_TASK)
    with pytest.raises(ValueError, match="completion payload"):
        await _executor(SimpleNamespace()).execute(
            replace(command, completion=None),
            actor,
        )
