"""Durable dispatcher retry, support and recovery edge behaviour."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import istari_service.workflow_command_dispatch as dispatch_module
from istari_service.domain import Actor, RequestRecord, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    UserRole,
    WorkflowOutbox,
    WorkflowTaskStatus,
)
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.schemas.work import CloseRequest
from istari_service.work_command_types import PendingWorkCommand, WorkCommandType
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowRequestRejected,
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
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher


def _state(
    command_type: WorkCommandType = WorkCommandType.CLAIM_TASK,
) -> tuple[Actor, WorkRecord, PendingWorkCommand, WorkflowOutbox]:
    actor = Actor(
        id=uuid4(),
        username="triage@example.test",
        display_name="Synthetic Triage",
        role=UserRole.INTAKE_TRIAGE,
        scope="Shared queue",
    )
    request = RequestRecord(
        id=uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.TRIAGE_REVIEW,
        assigned_delivery_team=None,
        assigned_specialist_id=None,
        version=1,
    )
    work = WorkRecord(
        id=uuid4(),
        request=request,
        engine_task_key="task-1",
        process_instance_key="process-1",
        element_id="triage-review",
        task_status=(
            WorkflowTaskStatus.CLAIM_PENDING
            if command_type is WorkCommandType.CLAIM_TASK
            else WorkflowTaskStatus.COMPLETION_PENDING
        ),
        assignee_id=actor.id,
        completed_at=None,
    )
    completion = (
        None
        if command_type is WorkCommandType.CLAIM_TASK
        else CloseRequest(action="close", reason="Synthetic closure reason")
    )
    outbox = WorkflowOutbox(
        request_id=request.id,
        event_type=command_type.value,
        payload={},
        idempotency_key=f"synthetic-{uuid4()}",
        status=OutboxStatus.PROCESSING,
        attempts=1,
    )
    command = PendingWorkCommand(
        outbox_id=outbox.id,
        command_type=command_type,
        work_id=work.id,
        task_key="task-1",
        process_instance_key="process-1",
        element_id="triage-review",
        actor_id=actor.id,
        request_version=1,
        request_status=RequestStatus.TRIAGE_REVIEW,
        attempts=1,
        completion=completion,
    )
    return actor, work, command, outbox


def _dispatcher(engine: object) -> WorkflowCommandDispatcher:
    return WorkflowCommandDispatcher(  # type: ignore[arg-type]
        SimpleNamespace(),
        engine,
        lookup_policy=TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            maximum_delay_seconds=0,
        ),
    )


@pytest.mark.parametrize("queued", [False, True])
async def test_claim_conflict_distinguishes_retry_from_final_conflict(
    monkeypatch: pytest.MonkeyPatch,
    queued: bool,
) -> None:
    actor, work, command, outbox = _state()
    conflict = WorkflowConflict("claim_task", 409)
    engine = SimpleNamespace(claim_task=AsyncMock(side_effect=conflict))
    dispatcher = _dispatcher(engine)

    async def recover(*_args: object) -> bool:
        outbox.status = OutboxStatus.PENDING if queued else OutboxStatus.FAILED
        return False

    monkeypatch.setattr(dispatcher, "_recover_claim", recover)
    result = await dispatcher._claim(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    if queued:
        assert isinstance(result, WorkflowEngineUnavailable)
    else:
        assert result is conflict


async def test_claim_outage_and_failed_projection_are_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, work, command, outbox = _state()
    outage = WorkflowEngineUnavailable("synthetic outage")
    dispatcher = _dispatcher(SimpleNamespace(claim_task=AsyncMock(side_effect=outage)))
    retries: list[object] = []

    async def retry(*args: object, **_kwargs: object) -> None:
        retries.extend(args)

    monkeypatch.setattr(dispatch_module, "schedule_retry", retry)
    result = await dispatcher._claim(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    assert result is outage
    assert retries

    dispatcher = _dispatcher(SimpleNamespace(claim_task=AsyncMock(return_value=None)))

    async def missing_projection(*_args: object, **_kwargs: object) -> None:
        return None

    failures: list[object] = []

    async def support(*args: object) -> None:
        failures.extend(args)

    monkeypatch.setattr(SqlAlchemyWorkRepository, "finalise_claim", missing_projection)
    monkeypatch.setattr(dispatch_module, "mark_support_failure", support)
    result = await dispatcher._claim(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    assert isinstance(result, WorkflowRequestRejected)
    assert failures


@pytest.mark.parametrize("mode", ["invisible", "unassigned", "competing"])
async def test_claim_recovery_handles_unproven_and_competing_state(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    actor, work, command, outbox = _state()
    dispatcher = _dispatcher(SimpleNamespace())
    retries: list[str] = []
    competitors: list[WorkflowTask] = []

    async def retry(*_args: object, **_kwargs: object) -> None:
        retries.append(mode)

    async def competitor(
        _session: object,
        _outbox: object,
        _work: object,
        task: WorkflowTask,
    ) -> None:
        competitors.append(task)

    if mode == "invisible":

        async def lookup(*_args: object, **_kwargs: object) -> WorkflowTask:
            raise WorkflowTaskNotVisible("not visible")

    else:
        assignee = None if mode == "unassigned" else str(uuid4())

        async def lookup(*_args: object, **_kwargs: object) -> WorkflowTask:
            return WorkflowTask(
                task_key=command.task_key,
                process_instance_key=command.process_instance_key,
                element_id=command.element_id,
                state=WorkflowTaskState.CREATED,
                assignee=assignee,
            )

    monkeypatch.setattr(dispatch_module, "wait_for_active_task", lookup)
    monkeypatch.setattr(dispatch_module, "schedule_retry", retry)
    monkeypatch.setattr(dispatch_module, "project_competing_claim", competitor)
    assert not await dispatcher._recover_claim(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    assert bool(retries) is (mode != "competing")
    assert bool(competitors) is (mode == "competing")


async def test_completion_retries_engine_and_proof_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, work, command, outbox = _state(WorkCommandType.COMPLETE_TASK)
    outage = WorkflowEngineUnavailable("synthetic outage")
    dispatcher = _dispatcher(
        SimpleNamespace(complete_task=AsyncMock(side_effect=outage))
    )
    retries: list[object] = []

    async def retry(*args: object, **_kwargs: object) -> None:
        retries.extend(args)

    monkeypatch.setattr(dispatch_module, "schedule_retry", retry)
    result = await dispatcher._complete(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    assert result is outage
    assert retries

    missing = WorkflowTaskNotFound("complete_task", 404)
    dispatcher = _dispatcher(
        SimpleNamespace(complete_task=AsyncMock(side_effect=missing))
    )

    async def no_proof(*_args: object) -> None:
        raise WorkflowTaskNotVisible("not proven")

    monkeypatch.setattr(dispatcher, "_completion_proof", no_proof)
    result = await dispatcher._complete(  # type: ignore[arg-type]
        SimpleNamespace(), outbox, command, actor, work
    )
    assert isinstance(result, WorkflowTaskNotVisible)


async def test_completion_proof_is_fail_closed_for_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _actor, _work, command, _outbox = _state(WorkCommandType.COMPLETE_TASK)
    dispatcher = _dispatcher(SimpleNamespace())

    async def invisible(*_args: object, **_kwargs: object) -> WorkflowTask:
        raise WorkflowTaskNotVisible("not visible")

    monkeypatch.setattr(dispatch_module, "wait_for_active_task", invisible)
    assert await dispatcher._completion_proof(command, "next-element", False) is None
    with pytest.raises(WorkflowTaskNotVisible):
        await dispatcher._completion_proof(command, "next-element", True)

    for state in (WorkflowProcessState.ACTIVE, WorkflowProcessState.TERMINATED):
        engine = SimpleNamespace(
            find_process_state=AsyncMock(
                return_value=WorkflowProcessSnapshot("process-1", state)
            )
        )
        dispatcher = _dispatcher(engine)
        with pytest.raises(WorkflowTaskNotVisible, match="not proven"):
            await dispatcher._completion_proof(command, None, True)

    completed = SimpleNamespace(
        find_process_state=AsyncMock(
            return_value=WorkflowProcessSnapshot(
                "process-1", WorkflowProcessState.COMPLETED
            )
        )
    )
    assert await _dispatcher(completed)._completion_proof(command, None, True) is None


async def test_complete_rejects_missing_stored_payload() -> None:
    actor, work, command, outbox = _state(WorkCommandType.COMPLETE_TASK)
    command = replace(command, completion=None)
    dispatcher = _dispatcher(SimpleNamespace())
    with pytest.raises(InvalidAction):
        await dispatcher._complete(  # type: ignore[arg-type]
            SimpleNamespace(), outbox, command, actor, work
        )
