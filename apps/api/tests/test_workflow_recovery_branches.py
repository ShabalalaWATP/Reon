"""Focused dispatcher and reconciler recovery branch coverage."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

import istari_service.workflow_maintenance as maintenance_module
from conftest import ApiHarness
from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowOutbox,
)
from istari_service.work_command_types import WorkCommandType
from istari_service.workflow.errors import WorkflowRequestRejected
from istari_service.workflow.types import StartedProcess
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher
from istari_service.workflow_dispatch import PendingStart, WorkflowOutboxDispatcher
from istari_service.workflow_maintenance import WorkflowReconciler
from test_coverage_dispatch_reconcile import (
    SearchEngine,
    prepare_candidate,
    workflow_task,
)

OUTBOX_ID = UUID("00000000-0000-4000-8000-000000000201")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000202")
REQUESTER_ID = UUID("00000000-0000-4000-8000-000000000203")


class StubTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class StubSession:
    def __init__(
        self,
        *,
        scalar_value: object | None = None,
        get_value: object | None = None,
    ) -> None:
        self.scalar_value = scalar_value
        self.get_value = get_value

    def __call__(self) -> StubSession:
        return self

    async def __aenter__(self) -> StubSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin(self) -> StubTransaction:
        return StubTransaction()

    async def scalar(self, _statement: object) -> object | None:
        return self.scalar_value

    async def get(self, _model: type[object], _identity: object) -> object | None:
        return self.get_value


async def test_command_dispatcher_handles_no_row_and_invalid_stored_command() -> None:
    empty = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(),
        SimpleNamespace(),
    )
    assert not await empty.dispatch_once()

    outbox = WorkflowOutbox(
        id=OUTBOX_ID,
        request_id=REQUEST_ID,
        event_type=WorkCommandType.COMPLETE_TASK.value,
        payload={},
        idempotency_key="synthetic-invalid-command",
        status=OutboxStatus.PENDING,
        attempts=0,
        lease_generation=0,
    )
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(scalar_value=outbox),
        SimpleNamespace(),
    )
    with pytest.raises(WorkflowRequestRejected):
        await dispatcher.dispatch(OUTBOX_ID)
    assert outbox.status is OutboxStatus.FAILED
    assert outbox.attempts == 1


async def test_start_dispatcher_tolerates_instance_removed_before_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = SimpleNamespace(id=REQUEST_ID)
    sessions = StubSession(scalar_value=None, get_value=request)
    dispatcher = WorkflowOutboxDispatcher(  # type: ignore[arg-type]
        sessions,
        SimpleNamespace(),
        process_id="service_request",
    )
    pending = PendingStart(
        outbox_id=OUTBOX_ID,
        request_id=REQUEST_ID,
        requester_id=REQUESTER_ID,
        attempts=1,
        lease_owner="synthetic-lease",
        lease_generation=1,
    )
    started = StartedProcess(
        process_instance_key="process-1",
        process_definition_key="definition-1",
        process_definition_id="service_request",
        process_definition_version=1,
        business_id=str(REQUEST_ID),
    )
    locked: list[PendingStart] = []

    async def current_lease(_session: object, value: PendingStart) -> object:
        locked.append(value)
        return object()

    monkeypatch.setattr(dispatcher, "_lock_current_lease", current_lease)
    await dispatcher._record_success(pending, started, None)
    assert locked == [pending]


async def test_reconciler_rejects_task_with_unexpected_element(
    api_harness: ApiHarness,
) -> None:
    await prepare_candidate(api_harness)
    task = replace(workflow_task(), element_id="coordination_review")
    engine = SearchEngine((task,))

    assert not await WorkflowReconciler(  # type: ignore[arg-type]
        api_harness.sessions,
        engine,
    ).reconcile_once()


async def test_reconciler_increments_version_when_projection_changes_status(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = await prepare_candidate(api_harness)
    async with api_harness.sessions() as session:
        before = await session.get(ServiceRequest, request_id)
        assert before is not None
        prior_version = before.version

    monkeypatch.setattr(
        maintenance_module,
        "status_for_element",
        lambda _element_id: RequestStatus.COORDINATION_REVIEW,
    )
    engine = SearchEngine((workflow_task(),))
    assert await WorkflowReconciler(  # type: ignore[arg-type]
        api_harness.sessions,
        engine,
    ).reconcile_once()

    async with api_harness.sessions() as session:
        updated = await session.get(ServiceRequest, request_id)
        assert updated is not None
        assert updated.status is RequestStatus.COORDINATION_REVIEW
        assert updated.version == prior_version + 1
