"""Durable workflow-cancellation retry and fencing behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from sqlalchemy import select

from api_helpers import submit_request
from conftest import ApiHarness
from mist_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from mist_service.workflow.errors import WorkflowTaskNotFound
from mist_service.workflow.types import (
    CancelProcessCommand,
    ProcessStateQuery,
    WorkflowProcessSnapshot,
    WorkflowProcessState,
)
from mist_service.workflow_cancellation_dispatch import (
    CANCELLATION_RETRY,
    CANCELLATION_SUPPORT,
    PendingCancellation,
    WorkflowCancellationDispatcher,
)
from workflow_test_support import FakeWorkflowEngine


async def _cancelled_request(harness: ApiHarness) -> UUID:
    request_id = UUID(await submit_request(harness))
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    response = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": detail.json()["version"],
            "reason": "The synthetic requirement has been withdrawn.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200
    return request_id


async def _cancellation_outbox(
    harness: ApiHarness,
    request_id: UUID,
) -> WorkflowOutbox:
    async with harness.sessions() as session:
        outbox = await session.scalar(
            select(WorkflowOutbox).where(
                WorkflowOutbox.request_id == request_id,
                WorkflowOutbox.event_type == "CANCEL_PROCESS",
            )
        )
        assert outbox is not None
        return outbox


async def test_cancellation_outage_retries_then_escalates(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    harness.workflow.reachable = False
    dispatcher = WorkflowCancellationDispatcher(
        harness.sessions,
        harness.workflow,
        max_attempts=2,
    )

    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(
                WorkflowOutbox.request_id == request_id,
                WorkflowOutbox.event_type == "CANCEL_PROCESS",
            )
        )
        assert outbox is not None
        assert outbox.status is OutboxStatus.PENDING
        assert outbox.last_error == CANCELLATION_RETRY
        outbox.available_at = datetime.now(UTC)

    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session:
        outbox = await session.scalar(
            select(WorkflowOutbox).where(
                WorkflowOutbox.request_id == request_id,
                WorkflowOutbox.event_type == "CANCEL_PROCESS",
            )
        )
        request = await session.get(ServiceRequest, request_id)
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert outbox is not None and outbox.status is OutboxStatus.FAILED
        assert outbox.last_error == CANCELLATION_SUPPORT
        assert request is not None and request.workflow_error == CANCELLATION_SUPPORT
        assert instance is not None and instance.last_error == CANCELLATION_SUPPORT


async def test_missing_process_identity_is_bounded_and_visible(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    async with harness.sessions() as session, session.begin():
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert instance is not None
        instance.process_instance_key = None

    dispatcher = WorkflowCancellationDispatcher(
        harness.sessions,
        harness.workflow,
        max_attempts=2,
    )
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.PENDING
    assert outbox.last_error == CANCELLATION_RETRY
    async with harness.sessions() as session, session.begin():
        current = await session.get(WorkflowOutbox, outbox.id)
        assert current is not None
        current.available_at = datetime.now(UTC)
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.FAILED
    assert outbox.last_error == CANCELLATION_SUPPORT
    assert harness.workflow.cancellation_commands == ()


async def test_stale_or_already_terminated_commands_do_not_call_engine(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    async with harness.sessions() as session, session.begin():
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert instance is not None
        instance.status = WorkflowInstanceStatus.TERMINATED

    dispatcher = WorkflowCancellationDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.SENT
    assert harness.workflow.cancellation_commands == ()


async def test_command_for_non_cancelled_request_fails_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.TRIAGE_REVIEW

    dispatcher = WorkflowCancellationDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.FAILED
    assert outbox.last_error == CANCELLATION_SUPPORT


class _AlreadyTerminatedEngine(FakeWorkflowEngine):
    async def cancel_process(self, _command: CancelProcessCommand) -> None:
        raise WorkflowTaskNotFound("cancel_process", 404)

    async def find_process_state(
        self,
        query: ProcessStateQuery,
    ) -> WorkflowProcessSnapshot | None:
        return WorkflowProcessSnapshot(
            query.process_instance_key,
            WorkflowProcessState.TERMINATED,
        )


class _StillActiveEngine(_AlreadyTerminatedEngine):
    async def find_process_state(
        self,
        query: ProcessStateQuery,
    ) -> WorkflowProcessSnapshot | None:
        return WorkflowProcessSnapshot(
            query.process_instance_key,
            WorkflowProcessState.ACTIVE,
        )


async def test_remote_terminated_proof_makes_recovery_idempotent(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    dispatcher = WorkflowCancellationDispatcher(
        harness.sessions,
        _AlreadyTerminatedEngine(),
    )
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.SENT


async def test_not_found_without_terminated_proof_remains_retryable(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    dispatcher = WorkflowCancellationDispatcher(
        harness.sessions,
        _StillActiveEngine(),
    )
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.PENDING
    assert outbox.last_error == CANCELLATION_RETRY


async def test_missing_local_instance_fails_the_command_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    async with harness.sessions() as session, session.begin():
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert instance is not None
        await session.delete(instance)

    dispatcher = WorkflowCancellationDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch_once()
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.FAILED
    assert outbox.last_error == CANCELLATION_SUPPORT


async def test_stale_lease_cannot_record_success(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _cancelled_request(harness)
    dispatcher = WorkflowCancellationDispatcher(harness.sessions, harness.workflow)
    pending, handled = await dispatcher._claim_next()
    assert handled and pending is not None
    async with harness.sessions() as session, session.begin():
        outbox = await session.get(WorkflowOutbox, pending.outbox_id)
        assert outbox is not None
        outbox.lease_owner = "replacement-worker"

    await dispatcher._record_success(pending)
    await dispatcher._record_retry(pending)
    outbox = await _cancellation_outbox(harness, request_id)
    assert outbox.status is OutboxStatus.PROCESSING
    assert outbox.lease_owner == "replacement-worker"


class _Context:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(self, *_values: object) -> None:
        return None


class _MissingProjectionSession:
    def __init__(self, outbox: WorkflowOutbox) -> None:
        self.scalar = AsyncMock(side_effect=[outbox, None])
        self.get = AsyncMock(return_value=None)

    async def __aenter__(self) -> _MissingProjectionSession:
        return self

    async def __aexit__(self, *_values: object) -> None:
        return None

    def begin(self) -> _Context:
        return _Context(None)


async def test_terminal_recording_tolerates_missing_local_projections() -> None:
    request_id = UUID("00000000-0000-4000-8000-000000000031")
    outbox_id = UUID("00000000-0000-4000-8000-000000000032")
    pending = PendingCancellation(
        outbox_id,
        request_id,
        "2251799813685250",
        1,
        "worker",
        1,
    )
    outbox = cast(
        WorkflowOutbox,
        SimpleNamespace(
            status=OutboxStatus.PROCESSING,
            lease_owner="worker",
            sent_at=None,
            last_error=None,
        ),
    )
    session = _MissingProjectionSession(outbox)
    dispatcher = WorkflowCancellationDispatcher(
        cast(Any, lambda: session),
        FakeWorkflowEngine(),
    )

    await dispatcher._record_success(pending)
    assert outbox.status is OutboxStatus.SENT

    retry_outbox = cast(
        WorkflowOutbox,
        SimpleNamespace(
            status=OutboxStatus.PROCESSING,
            lease_owner="worker",
            last_error=None,
            available_at=datetime.now(UTC),
        ),
    )
    retry_session = _MissingProjectionSession(retry_outbox)
    exhausted = WorkflowCancellationDispatcher(
        cast(Any, lambda: retry_session),
        FakeWorkflowEngine(),
        max_attempts=1,
    )
    await exhausted._record_retry(pending)
    assert retry_outbox.status is OutboxStatus.FAILED
