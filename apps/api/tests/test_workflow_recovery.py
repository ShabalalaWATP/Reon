"""Bounded workflow recovery tests."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.models import (
    OutboxStatus,
    RequestEvent,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from istari_service.workflow_recovery import (
    RECOVERY_CONFIRMATION,
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
        command.last_error = "content-free failure"
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
