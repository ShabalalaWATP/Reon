"""Workflow outage, retry and eventual-consistency behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from api_helpers import current_item, submit_request
from conftest import ApiHarness, request_payload
from mist_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowOutbox,
    WorkflowTask,
)
from mist_service.workflow.lookup import TaskLookupPolicy
from mist_service.workflow_command_dispatch import WorkflowCommandDispatcher
from mist_service.workflow_dispatch import WorkflowOutboxDispatcher
from mist_service.workflow_maintenance import WorkflowReconciler


async def _create_without_dispatch(harness: ApiHarness) -> UUID:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def test_start_outage_retries_without_duplicate_process(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _create_without_dispatch(harness)
    harness.workflow.reachable = False
    dispatcher = WorkflowOutboxDispatcher(
        harness.sessions,
        harness.workflow,
        process_id=harness.settings.camunda_process_id,
        max_attempts=3,
    )
    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(select(WorkflowOutbox))
        request = await session.get(ServiceRequest, request_id)
        assert outbox is not None and request is not None
        assert outbox.status == OutboxStatus.PENDING
        assert request.status == RequestStatus.ROUTING_PENDING
        assert request.workflow_error == "Workflow start will be retried."
        outbox.available_at = datetime.now(UTC)

    harness.workflow.reachable = True
    assert await dispatcher.dispatch_once()
    assert not await dispatcher.dispatch_once()
    async with harness.sessions() as session:
        outbox = await session.scalar(select(WorkflowOutbox))
        request = await session.get(ServiceRequest, request_id)
        assert outbox is not None and request is not None
        assert outbox.status == OutboxStatus.SENT
        assert request.status == RequestStatus.TRIAGE_REVIEW
    assert len(harness.workflow.start_commands) == 1


async def test_exhausted_start_is_visible_for_support(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await _create_without_dispatch(harness)
    harness.workflow.reachable = False
    dispatcher = WorkflowOutboxDispatcher(
        harness.sessions,
        harness.workflow,
        process_id=harness.settings.camunda_process_id,
        max_attempts=1,
    )
    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session:
        outbox = await session.scalar(select(WorkflowOutbox))
        request = await session.get(ServiceRequest, request_id)
        assert outbox is not None and request is not None
        assert outbox.status == OutboxStatus.FAILED
        assert request.workflow_error == "Workflow start needs support."


async def test_missing_initial_projection_is_reconciled(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.workflow._visibility_lag_searches = 2
    request_id = await _create_without_dispatch(harness)
    dispatcher = WorkflowOutboxDispatcher(
        harness.sessions,
        harness.workflow,
        process_id=harness.settings.camunda_process_id,
        lookup_policy=TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            backoff_multiplier=1,
            maximum_delay_seconds=0,
        ),
    )
    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        tasks = (await session.scalars(select(WorkflowTask))).all()
        assert request is not None and request.workflow_error
        assert tasks == []

    reconciler = WorkflowReconciler(harness.sessions, harness.workflow)
    assert not await reconciler.reconcile_once()
    assert await reconciler.reconcile_once()
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        tasks = (await session.scalars(select(WorkflowTask))).all()
        assert request is not None and request.workflow_error is None
        assert len(tasks) == 1


async def test_claim_and_completion_outage_leave_durable_pending_intents(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    listing = await harness.client.get("/api/v1/work-items")
    item = listing.json()["items"][0]
    harness.workflow.reachable = False
    claim = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/claim",
        headers=harness.mutation_headers(),
    )
    assert claim.status_code == 503
    assert "recorded" in claim.json()["detail"]["message"]
    pending = (await harness.client.get("/api/v1/work-items")).json()["items"][0]
    assert pending["status"] == "CLAIM_PENDING"
    assert pending["availableActions"] == []
    harness.workflow.reachable = True
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.event_type == "CLAIM_TASK")
        )
        assert outbox is not None
        outbox.available_at = datetime.now(UTC)
    dispatcher = WorkflowCommandDispatcher(
        harness.sessions,
        harness.workflow,
        lookup_policy=TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            maximum_delay_seconds=0,
        ),
    )
    assert await dispatcher.dispatch_once()
    item = await current_item(harness)
    assert item["status"] == "CLAIMED"
    harness.workflow.reachable = False
    complete = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json={"action": "close", "reason": "A fictional reason."},
        headers=harness.mutation_headers(),
    )
    assert complete.status_code == 503
    pending = (await harness.client.get("/api/v1/work-items")).json()["items"][0]
    assert pending["status"] == "COMPLETION_PENDING"
    assert pending["availableActions"] == []
    async with harness.sessions() as session:
        request = await session.scalar(select(ServiceRequest))
        assert request is not None
        assert request.status == RequestStatus.TRIAGE_REVIEW
    harness.workflow.reachable = True
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.event_type == "COMPLETE_TASK")
        )
        assert outbox is not None
        outbox.available_at = datetime.now(UTC)
    assert await dispatcher.dispatch_once()
    async with harness.sessions() as session:
        request = await session.scalar(select(ServiceRequest))
        assert request is not None
        assert request.status == RequestStatus.CLOSED_NOT_PROGRESSED


async def test_readiness_reports_workflow_outage(api_harness: ApiHarness) -> None:
    harness = api_harness
    ready = await harness.client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    harness.workflow.reachable = False
    unavailable = await harness.client.get("/ready")
    assert unavailable.status_code == 503
    assert unavailable.json()["checks"]["workflow"] == "unavailable"
    health = await harness.client.get("/health")
    assert health.status_code == 200
