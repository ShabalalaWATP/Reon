"""Bounded workflow recovery tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from api_helpers import submit_request
from conftest import ApiHarness, request_payload
from istari_service.models import (
    OutboxStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.request_event_models import RequestEvent
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher
from istari_service.workflow_command_results import (
    RETRY_EXHAUSTED_MESSAGE,
    SUPPORT_MESSAGE,
)
from istari_service.workflow_recovery import (
    RECOVERY_CONFIRMATION,
    _recoverable_task_status,
    recover_failed_workflow,
)


async def test_failed_start_is_inspected_then_explicitly_requeued(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    request_id = UUID(response.json()["id"])
    async with harness.sessions() as session, session.begin():
        command = await session.scalar(select(WorkflowOutbox))
        instance = await session.scalar(select(WorkflowInstance))
        assert command is not None and instance is not None
        command.status = OutboxStatus.FAILED
        command.attempts = 30
        command.last_error = "Workflow start is unavailable."
        instance.status = WorkflowInstanceStatus.ERROR
        instance.last_error = "content-free failure"

    async with harness.sessions() as session:
        dry_run = await recover_failed_workflow(session, request_id)
    assert dry_run.failed_commands == 1
    assert dry_run.requeued_commands == 0
    assert not dry_run.applied

    async with harness.sessions() as session, session.begin():
        report = await recover_failed_workflow(
            session,
            request_id,
            apply=True,
            confirmation=RECOVERY_CONFIRMATION,
        )
    assert report.requeued_commands == 1 and report.applied
    async with harness.sessions() as session:
        command = await session.scalar(select(WorkflowOutbox))
        instance = await session.scalar(select(WorkflowInstance))
        events = list(
            await session.scalars(
                select(RequestEvent).where(RequestEvent.request_id == request_id)
            )
        )
    assert command is not None and command.status == OutboxStatus.PENDING
    assert command.attempts == 0 and command.last_error is None
    assert (
        instance is not None and instance.status == WorkflowInstanceStatus.START_PENDING
    )
    assert any(event.type == "workflow_recovery_queued" for event in events)


async def test_recovery_rejects_wrong_confirmation_and_unknown_request(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session:
        try:
            await recover_failed_workflow(
                session, uuid4(), apply=True, confirmation="wrong"
            )
        except ValueError as error:
            assert "exact confirmation" in str(error)
        else:
            raise AssertionError("wrong confirmation was accepted")
        try:
            await recover_failed_workflow(session, uuid4())
        except ValueError as error:
            assert "does not exist" in str(error)
        else:
            raise AssertionError("unknown request was accepted")


async def test_exhausted_claim_recovery_restores_pending_state_and_dispatches(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    await harness.login("admin4")
    item = (await harness.client.get("/api/v1/work-items")).json()["items"][0]
    harness.workflow.reachable = False
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/claim",
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 503
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.event_type == "CLAIM_TASK")
        )
        task = await session.get(WorkflowTask, UUID(item["id"]))
        assert outbox is not None and task is not None
        outbox.status = OutboxStatus.FAILED
        outbox.last_error = RETRY_EXHAUSTED_MESSAGE
        task.status = WorkflowTaskStatus.ERROR
    async with harness.sessions() as session, session.begin():
        report = await recover_failed_workflow(
            session,
            request_id,
            apply=True,
            confirmation=RECOVERY_CONFIRMATION,
        )
    assert report.requeued_commands == 1
    async with harness.sessions() as session:
        task = await session.get(WorkflowTask, UUID(item["id"]))
        assert task is not None
        assert task.status is WorkflowTaskStatus.CLAIM_PENDING
    harness.workflow.reachable = True
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.event_type == "CLAIM_TASK")
        )
        assert outbox is not None
        outbox.available_at = datetime.now(UTC)
    assert await WorkflowCommandDispatcher(
        harness.sessions,
        harness.workflow,
    ).dispatch_once()


async def test_permanent_command_failure_is_not_requeued(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    async with harness.sessions() as session, session.begin():
        command = await session.scalar(select(WorkflowOutbox))
        assert command is not None
        command.status = OutboxStatus.FAILED
        command.last_error = SUPPORT_MESSAGE
    async with harness.sessions() as session, session.begin():
        report = await recover_failed_workflow(
            session,
            request_id,
            apply=True,
            confirmation=RECOVERY_CONFIRMATION,
        )
    assert report.failed_commands == 1
    assert report.requeued_commands == 0
    assert not report.applied


def test_recovery_classifies_completion_and_unknown_failed_commands() -> None:
    command = WorkflowOutbox(
        request_id=uuid4(),
        event_type="COMPLETE_TASK",
        payload={},
        idempotency_key="synthetic-completion-recovery",
        status=OutboxStatus.FAILED,
        last_error=RETRY_EXHAUSTED_MESSAGE,
    )
    assert _recoverable_task_status(command) is WorkflowTaskStatus.COMPLETION_PENDING
    command.event_type = "UNKNOWN_COMMAND"
    assert _recoverable_task_status(command) is False
    command.event_type = "CLAIM_TASK"
    command.last_error = SUPPORT_MESSAGE
    assert _recoverable_task_status(command) is False
