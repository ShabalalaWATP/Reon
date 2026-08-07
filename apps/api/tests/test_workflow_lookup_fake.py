"""Behaviour tests for the deterministic fake workflow engine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from istari_service.models import RequestStatus
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    InvalidWorkflowTransition,
    UnexpectedWorkflowTask,
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowTaskNotFound,
)
from istari_service.workflow.fake import FakeWorkflowEngine
from istari_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    CompleteTaskCommand,
    DeliveryTeamId,
    ProcessStateQuery,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowAction,
    WorkflowProcessSnapshot,
    WorkflowProcessState,
    WorkflowTask,
)

REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_REQUEST_ID = UUID("00000000-0000-4000-8000-000000000004")
REQUESTER_ID = UUID("00000000-0000-4000-8000-000000000002")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000005")
SPECIALIST_ID = UUID("00000000-0000-4000-8000-000000000003")


def command(
    request_id: UUID = REQUEST_ID,
    *,
    requester_id: UUID = REQUESTER_ID,
    version: int = -1,
    tenant_id: str | None = None,
) -> StartProcessCommand:
    return StartProcessCommand(
        "service_request", request_id, requester_id, version, tenant_id
    )


@pytest.mark.asyncio
async def test_fake_start_is_deterministic_idempotent_and_conflict_safe() -> None:
    engine = FakeWorkflowEngine()
    first = await engine.start_process(command())
    replay = await engine.start_process(command())
    second = await engine.start_process(command(OTHER_REQUEST_ID))

    assert isinstance(engine, WorkflowEngine)
    assert replay is first
    assert first.process_definition_version == 1
    assert second.process_definition_key == first.process_definition_key
    assert second.process_instance_key != first.process_instance_key
    assert len(engine.start_commands) == 3
    assert len(engine.active_tasks) == 2
    with pytest.raises(WorkflowConflict) as caught:
        await engine.start_process(command(requester_id=OTHER_USER_ID))
    assert caught.value.operation == "start_process"
    assert caught.value.status_code == 409


@pytest.mark.asyncio
async def test_fake_definition_identity_includes_version_and_tenant() -> None:
    engine = FakeWorkflowEngine()
    first = await engine.start_process(command(version=2, tenant_id="tenant-a"))
    second = await engine.start_process(
        command(OTHER_REQUEST_ID, version=3, tenant_id="tenant-a")
    )

    assert first.process_definition_version == 2
    assert first.process_definition_key != second.process_definition_key


@pytest.mark.asyncio
async def test_fake_process_recovery_requires_every_identity_field() -> None:
    engine = FakeWorkflowEngine()
    started = await engine.start_process(command(version=2, tenant_id="tenant-a"))

    assert (
        await engine.find_started_process(
            StartedProcessQuery("service_request", OTHER_REQUEST_ID)
        )
        is None
    )
    assert (
        await engine.find_started_process(
            StartedProcessQuery("different", REQUEST_ID, 2, "tenant-a")
        )
        is None
    )
    assert (
        await engine.find_started_process(
            StartedProcessQuery("service_request", REQUEST_ID, 3, "tenant-a")
        )
        is None
    )
    assert (
        await engine.find_started_process(
            StartedProcessQuery("service_request", REQUEST_ID, 2, "tenant-b")
        )
        is None
    )
    assert (
        await engine.find_started_process(
            StartedProcessQuery("service_request", REQUEST_ID, -1, "tenant-a")
        )
        == started
    )


@pytest.mark.asyncio
async def test_fake_search_models_eventual_visibility_and_exact_element() -> None:
    engine = FakeWorkflowEngine(visibility_lag_searches=2)
    started = await engine.start_process(command())
    exact = ActiveTaskQuery(started.process_instance_key, "intake_review")

    assert await engine.search_active_tasks(ActiveTaskQuery("missing")) == ()
    assert (
        await engine.search_active_tasks(
            ActiveTaskQuery(started.process_instance_key, "wrong")
        )
        == ()
    )
    assert await engine.search_active_tasks(exact) == ()
    assert await engine.search_active_tasks(exact) == ()
    assert len(await engine.search_active_tasks(exact)) == 1
    with pytest.raises(ValueError, match="negative"):
        FakeWorkflowEngine(visibility_lag_searches=-1)


async def current_task(
    engine: FakeWorkflowEngine,
    started: StartedProcess,
) -> WorkflowTask:
    tasks = await engine.search_active_tasks(
        ActiveTaskQuery(started.process_instance_key)
    )
    assert len(tasks) == 1
    return tasks[0]


async def complete_current(
    engine: FakeWorkflowEngine,
    started: StartedProcess,
    action: WorkflowAction,
    *,
    delivery_team_id: DeliveryTeamId | None = None,
    specialist_id: UUID | None = None,
) -> None:
    active = await current_task(engine, started)
    await engine.complete_task(
        CompleteTaskCommand(
            active.task_key,
            started.process_instance_key,
            active.element_id,
            action,
            delivery_team_id,
            specialist_id,
        )
    )


@pytest.mark.asyncio
async def test_fake_process_state_is_exact_and_becomes_terminal() -> None:
    engine = FakeWorkflowEngine()
    assert await engine.find_process_state(ProcessStateQuery("missing")) is None
    started = await engine.start_process(command())
    query = ProcessStateQuery(started.process_instance_key)

    assert await engine.find_process_state(query) == WorkflowProcessSnapshot(
        started.process_instance_key,
        WorkflowProcessState.ACTIVE,
    )
    await complete_current(engine, started, WorkflowAction.CLOSE)
    assert await engine.find_process_state(query) == WorkflowProcessSnapshot(
        started.process_instance_key,
        WorkflowProcessState.COMPLETED,
    )


@pytest.mark.asyncio
async def test_fake_claiming_is_atomic_and_does_not_override_assignments() -> None:
    engine = FakeWorkflowEngine()
    started = await engine.start_process(command())
    active = await current_task(engine, started)
    claim = ClaimTaskCommand(active.task_key, OTHER_USER_ID)

    with pytest.raises(WorkflowTaskNotFound):
        await engine.claim_task(ClaimTaskCommand("missing", OTHER_USER_ID))
    await engine.claim_task(claim)
    assert engine.claim_commands == (claim,)
    assert (await current_task(engine, started)).assignee == str(OTHER_USER_ID)
    with pytest.raises(WorkflowConflict):
        await engine.claim_task(ClaimTaskCommand(active.task_key, REQUESTER_ID))

    await complete_current(engine, started, WorkflowAction.REQUEST_INFORMATION)
    requester_task = await current_task(engine, started)
    assert requester_task.assignee == str(REQUESTER_ID)
    with pytest.raises(WorkflowConflict):
        await engine.claim_task(
            ClaimTaskCommand(requester_task.task_key, OTHER_USER_ID)
        )


@pytest.mark.asyncio
async def test_fake_completion_rejects_stale_or_mismatched_commands() -> None:
    engine = FakeWorkflowEngine()
    started = await engine.start_process(command())
    active = await current_task(engine, started)

    with pytest.raises(WorkflowTaskNotFound):
        await engine.complete_task(
            CompleteTaskCommand(
                "missing",
                started.process_instance_key,
                "intake_review",
                WorkflowAction.PROGRESS,
            )
        )
    with pytest.raises(UnexpectedWorkflowTask, match="another process"):
        await engine.complete_task(
            CompleteTaskCommand(
                active.task_key,
                "other-process",
                "intake_review",
                WorkflowAction.PROGRESS,
            )
        )
    with pytest.raises(UnexpectedWorkflowTask, match="element"):
        await engine.complete_task(
            CompleteTaskCommand(
                active.task_key,
                started.process_instance_key,
                "coordination_review",
                WorkflowAction.PROGRESS,
            )
        )
    with pytest.raises(InvalidWorkflowTransition):
        await engine.complete_task(
            CompleteTaskCommand(
                active.task_key,
                started.process_instance_key,
                "intake_review",
                WorkflowAction.RELEASE,
            )
        )
    assert engine.completion_commands == ()


@pytest.mark.asyncio
async def test_fake_runs_loops_assignment_rework_and_terminal_release() -> None:
    engine = FakeWorkflowEngine()
    started = await engine.start_process(command())
    actions: list[tuple[WorkflowAction, RequestStatus]] = [
        (WorkflowAction.PROGRESS, RequestStatus.COORDINATION_REVIEW),
        (WorkflowAction.HOLD, RequestStatus.ON_HOLD),
        (WorkflowAction.RESUME, RequestStatus.COORDINATION_REVIEW),
        (WorkflowAction.SEND_TO_ALLOCATION, RequestStatus.ALLOCATION_REVIEW),
    ]
    for action, status in actions:
        await complete_current(engine, started, action)
        assert engine.status_for_process(started.process_instance_key) is status
    await complete_current(
        engine,
        started,
        WorkflowAction.ALLOCATE,
        delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_B,
    )
    await complete_current(engine, started, WorkflowAction.RETURN_FOR_REALLOCATION)
    await complete_current(
        engine,
        started,
        WorkflowAction.ALLOCATE,
        delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A,
    )
    await complete_current(
        engine, started, WorkflowAction.ASSIGN, specialist_id=SPECIALIST_ID
    )
    assert (await current_task(engine, started)).assignee == str(SPECIALIST_ID)
    await complete_current(engine, started, WorkflowAction.SUBMIT)
    await complete_current(engine, started, WorkflowAction.CHANGES_REQUIRED)
    assert (
        engine.status_for_process(started.process_instance_key)
        is RequestStatus.REWORK_REQUIRED
    )
    assert (await current_task(engine, started)).assignee == str(SPECIALIST_ID)
    await complete_current(engine, started, WorkflowAction.SUBMIT)
    await complete_current(engine, started, WorkflowAction.APPROVE)
    await complete_current(engine, started, WorkflowAction.APPROVE)
    await complete_current(engine, started, WorkflowAction.RELEASE)

    assert (
        engine.status_for_process(started.process_instance_key)
        is RequestStatus.COMPLETED
    )
    assert (
        await engine.search_active_tasks(ActiveTaskQuery(started.process_instance_key))
        == ()
    )
    assert len(engine.completion_commands) == 14


@pytest.mark.asyncio
async def test_fake_unreachable_state_fails_commands_without_masking_readiness() -> (
    None
):
    engine = FakeWorkflowEngine(reachable=False)
    assert await engine.is_reachable() is False
    operations: tuple[Callable[[], Awaitable[object]], ...] = (
        lambda: engine.start_process(command()),
        lambda: engine.find_started_process(
            StartedProcessQuery("service_request", REQUEST_ID)
        ),
        lambda: engine.find_process_state(ProcessStateQuery("process")),
        lambda: engine.search_active_tasks(ActiveTaskQuery("process")),
        lambda: engine.claim_task(ClaimTaskCommand("task", REQUESTER_ID)),
        lambda: engine.complete_task(
            CompleteTaskCommand(
                "task", "process", "intake_review", WorkflowAction.PROGRESS
            )
        ),
    )
    for operation in operations:
        with pytest.raises(WorkflowEngineUnavailable):
            await operation()
