"""Outbox dispatcher failure, idempotency and projection edge coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from conftest import ApiHarness, request_payload
from mist_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowOutbox,
    WorkflowTaskStatus,
)
from mist_service.models import (
    WorkflowTask as StoredWorkflowTask,
)
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow.errors import WorkflowConflict
from mist_service.workflow.lookup import TaskLookupPolicy
from mist_service.workflow.types import (
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowTask,
    WorkflowTaskState,
)
from mist_service.workflow_dispatch import (
    PendingStart,
    WorkflowOutboxDispatcher,
    add_task_projection,
)


async def create_request(harness: ApiHarness) -> UUID:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def make_dispatcher(
    harness: ApiHarness,
    engine: WorkflowEngine | None = None,
) -> WorkflowOutboxDispatcher:
    return WorkflowOutboxDispatcher(
        harness.sessions,
        engine or harness.workflow,
        process_id=harness.settings.camunda_process_id,
        lookup_policy=TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            backoff_multiplier=1,
            maximum_delay_seconds=0,
        ),
    )


def started_process(request_id: UUID) -> StartedProcess:
    return StartedProcess(
        process_instance_key="synthetic-process-key",
        process_definition_key="synthetic-definition-key",
        process_definition_id="service-request-v1",
        process_definition_version=1,
        business_id=str(request_id),
    )


def visible_task(*, assignee: str | None = None, suffix: str = "edge") -> WorkflowTask:
    return WorkflowTask(
        task_key=f"synthetic-task-{suffix}",
        process_instance_key="synthetic-process-key",
        element_id="intake_review",
        state=WorkflowTaskState.CREATED,
        assignee=assignee,
    )


def pending_start(
    outbox_id: UUID,
    request_id: UUID,
    requester_id: UUID,
    *,
    attempts: int = 1,
    lease_owner: str = "synthetic-lease-owner",
    lease_generation: int = 1,
) -> PendingStart:
    return PendingStart(
        outbox_id,
        request_id,
        requester_id,
        attempts,
        lease_owner,
        lease_generation,
    )


class ConflictEngine:
    def __init__(self, existing: StartedProcess | None) -> None:
        self.existing = existing
        self.queries: list[StartedProcessQuery] = []

    async def start_process(self, _command: StartProcessCommand) -> StartedProcess:
        raise WorkflowConflict("start_process", 409)

    async def find_started_process(
        self, query: StartedProcessQuery
    ) -> StartedProcess | None:
        self.queries.append(query)
        return self.existing


async def test_conflicted_start_recovers_exact_process_or_reraises(
    api_harness: ApiHarness,
) -> None:
    request_id = uuid4()
    command = StartProcessCommand(
        process_definition_id="service-request-v1",
        request_id=request_id,
        requester_id=uuid4(),
    )
    existing = started_process(request_id)
    recovering_engine = ConflictEngine(existing)
    recovering = make_dispatcher(api_harness, cast(WorkflowEngine, recovering_engine))

    recovered = await recovering._start_idempotently(command)

    assert recovered is existing
    assert recovering_engine.queries == [StartedProcessQuery.from_start(command)]

    failing = make_dispatcher(api_harness, cast(WorkflowEngine, ConflictEngine(None)))
    with pytest.raises(WorkflowConflict):
        await failing._start_idempotently(command)


async def test_missing_request_marks_outbox_failed_safely(
    api_harness: ApiHarness,
) -> None:
    outbox_id = uuid4()
    async with api_harness.sessions() as session, session.begin():
        session.add(
            WorkflowOutbox(
                id=outbox_id,
                request_id=uuid4(),
                event_type="START_PROCESS",
                payload={},
                idempotency_key=f"synthetic-missing-{outbox_id}",
                status=OutboxStatus.PENDING,
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )

    assert not await make_dispatcher(api_harness).dispatch_once()
    async with api_harness.sessions() as session:
        outbox = await session.get(WorkflowOutbox, outbox_id)
        assert outbox is not None
        assert outbox.status == OutboxStatus.FAILED
        assert outbox.last_error == "Associated request is missing."


async def test_record_success_ignores_missing_and_already_sent_entities(
    api_harness: ApiHarness,
) -> None:
    dispatcher = make_dispatcher(api_harness)
    missing = pending_start(uuid4(), uuid4(), uuid4())
    await dispatcher._record_success(missing, started_process(missing.request_id), None)

    request_id = await create_request(api_harness)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        assert request is not None and outbox is not None
        outbox.status = OutboxStatus.SENT
        original_version = request.version
        pending = pending_start(outbox.id, request.id, request.requester_id)

    await dispatcher._record_success(
        pending, started_process(request_id), visible_task()
    )
    async with api_harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        count = await session.scalar(select(func.count(StoredWorkflowTask.id)))
        assert request is not None
        assert request.version == original_version
        assert count == 0


async def test_record_success_preserves_non_routing_request_status(
    api_harness: ApiHarness,
) -> None:
    request_id = await create_request(api_harness)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        assert request is not None and outbox is not None
        request.status = RequestStatus.TRIAGE_REVIEW
        pending = pending_start(outbox.id, request.id, request.requester_id)
        outbox.status = OutboxStatus.PROCESSING
        outbox.lease_owner = pending.lease_owner
        outbox.lease_generation = pending.lease_generation
        original_version = request.version

    await make_dispatcher(api_harness)._record_success(
        pending, started_process(request_id), visible_task()
    )
    async with api_harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        outbox = await session.get(WorkflowOutbox, pending.outbox_id)
        assert request is not None and outbox is not None
        assert request.status == RequestStatus.TRIAGE_REVIEW
        assert request.version == original_version
        assert outbox.status == OutboxStatus.SENT


async def test_record_retry_handles_absent_entities(api_harness: ApiHarness) -> None:
    dispatcher = make_dispatcher(api_harness)
    missing = pending_start(uuid4(), uuid4(), uuid4())
    await dispatcher._record_retry(missing)

    outbox_id = uuid4()
    async with api_harness.sessions() as session, session.begin():
        session.add(
            WorkflowOutbox(
                id=outbox_id,
                request_id=uuid4(),
                event_type="START_PROCESS",
                payload={},
                idempotency_key=f"synthetic-retry-{outbox_id}",
                status=OutboxStatus.PROCESSING,
                attempts=1,
                lease_owner="synthetic-lease-owner",
                lease_generation=1,
                available_at=datetime.now(UTC),
            )
        )
    pending = pending_start(outbox_id, uuid4(), uuid4())

    await dispatcher._record_retry(pending)

    async with api_harness.sessions() as session:
        outbox = await session.get(WorkflowOutbox, outbox_id)
        assert outbox is not None
        assert outbox.status == OutboxStatus.PENDING
        assert outbox.last_error == "Workflow start is unavailable."


async def test_superseded_start_worker_cannot_overwrite_current_lease(
    api_harness: ApiHarness,
) -> None:
    request_id = await create_request(api_harness)
    dispatcher = make_dispatcher(api_harness)
    first = await dispatcher._claim_next()
    assert first is not None
    async with api_harness.sessions() as session, session.begin():
        outbox = await session.get(WorkflowOutbox, first.outbox_id)
        assert outbox is not None
        outbox.available_at = datetime.now(UTC)

    second = await dispatcher._claim_next()
    assert second is not None
    assert second.lease_owner != first.lease_owner
    assert second.lease_generation == first.lease_generation + 1

    await dispatcher._record_retry(first)
    await dispatcher._record_success(
        first,
        started_process(request_id),
        visible_task(suffix="stale"),
    )
    async with api_harness.sessions() as session:
        outbox = await session.get(WorkflowOutbox, first.outbox_id)
        assert outbox is not None
        assert outbox.status == OutboxStatus.PROCESSING
        assert outbox.lease_owner == second.lease_owner
        assert outbox.lease_generation == second.lease_generation

    await dispatcher._record_success(
        second,
        started_process(request_id),
        visible_task(suffix="fenced"),
    )
    await dispatcher._record_retry(first)
    async with api_harness.sessions() as session:
        outbox = await session.get(WorkflowOutbox, first.outbox_id)
        request = await session.get(ServiceRequest, request_id)
        assert outbox is not None and request is not None
        assert outbox.status == OutboxStatus.SENT
        assert outbox.lease_owner is None
        assert request.status == RequestStatus.TRIAGE_REVIEW


async def test_projection_handles_assignees_and_existing_tasks(
    api_harness: ApiHarness,
) -> None:
    request_id = await create_request(api_harness)
    assignee_id = await api_harness.user_id("admin4")
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert request is not None and instance is not None
        request.status = RequestStatus.TRIAGE_REVIEW
        claimed = visible_task(assignee=str(assignee_id), suffix="claimed")
        invalid = visible_task(assignee="not-a-user-id", suffix="invalid")
        await add_task_projection(session, request, instance, claimed)
        await session.flush()
        await add_task_projection(session, request, instance, claimed)
        await add_task_projection(session, request, instance, invalid)

    async with api_harness.sessions() as session:
        tasks = (
            await session.scalars(
                select(StoredWorkflowTask).order_by(StoredWorkflowTask.task_key)
            )
        ).all()
        assert len(tasks) == 2
        by_key = {task.task_key: task for task in tasks}
        claimed_projection = by_key[claimed.task_key]
        invalid_projection = by_key[invalid.task_key]
        assert claimed_projection.status == WorkflowTaskStatus.CLAIMED
        assert claimed_projection.assignee_user_id == assignee_id
        assert claimed_projection.claimed_at is not None
        assert invalid_projection.status == WorkflowTaskStatus.OPEN
        assert invalid_projection.assignee_user_id is None
        assert invalid_projection.claimed_at is None
