"""Crash-window regressions for durable claim and completion commands."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select

from api_helpers import current_item, submit_request
from conftest import ApiHarness
from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.request_event_models import RequestEvent
from istari_service.workflow.types import ActiveTaskQuery
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher


async def _outbox(
    harness: ApiHarness,
    event_type: str,
) -> WorkflowOutbox:
    async with harness.sessions() as session:
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.event_type == event_type)
        )
        assert outbox is not None
        return outbox


async def _event_count(harness: ApiHarness, event_type: str) -> int:
    async with harness.sessions() as session:
        count = await session.scalar(
            select(func.count(RequestEvent.id)).where(RequestEvent.type == event_type)
        )
        return int(count or 0)


async def test_claim_recovers_after_engine_success_before_product_commit(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    item = (await harness.client.get("/api/v1/work-items")).json()["items"][0]
    original = SqlAlchemyWorkRepository.finalise_claim

    async def fail_after_engine(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected product projection failure")

    monkeypatch.setattr(SqlAlchemyWorkRepository, "finalise_claim", fail_after_engine)
    with pytest.raises(RuntimeError, match="injected product projection failure"):
        await harness.client.post(
            f"/api/v1/work-items/{item['id']}/claim",
            headers=harness.mutation_headers(),
        )

    outbox = await _outbox(harness, "CLAIM_TASK")
    async with harness.sessions() as session:
        task = await session.get(WorkflowTask, UUID(item["id"]))
        assert task is not None and task.status is WorkflowTaskStatus.CLAIM_PENDING
        assert outbox.status is OutboxStatus.PENDING
    engine_tasks = await harness.workflow.search_active_tasks(
        ActiveTaskQuery(outbox.payload["processInstanceKey"])
    )
    assert len(engine_tasks) == 1 and engine_tasks[0].assignee is not None
    assert await _event_count(harness, "workflow_claimed") == 0

    monkeypatch.setattr(SqlAlchemyWorkRepository, "finalise_claim", original)
    dispatcher = WorkflowCommandDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch(outbox.id)
    async with harness.sessions() as session:
        task = await session.get(WorkflowTask, UUID(item["id"]))
        recovered = await session.get(WorkflowOutbox, outbox.id)
        assert task is not None and task.status is WorkflowTaskStatus.CLAIMED
        assert recovered is not None and recovered.status is OutboxStatus.SENT
    assert await _event_count(harness, "workflow_claimed") == 1


async def test_completion_recovers_after_engine_success_before_product_commit(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    item = await current_item(harness)
    original = SqlAlchemyWorkRepository.apply_completion

    async def fail_after_engine(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected product projection failure")

    monkeypatch.setattr(
        SqlAlchemyWorkRepository,
        "apply_completion",
        fail_after_engine,
    )
    with pytest.raises(RuntimeError, match="injected product projection failure"):
        await harness.client.post(
            f"/api/v1/work-items/{item['id']}/complete",
            json={"action": "close", "reason": "A synthetic reason."},
            headers=harness.mutation_headers(),
        )

    outbox = await _outbox(harness, "COMPLETE_TASK")
    async with harness.sessions() as session:
        request = await session.scalar(select(ServiceRequest))
        task = await session.get(WorkflowTask, UUID(item["id"]))
        assert request is not None and request.status is RequestStatus.TRIAGE_REVIEW
        assert task is not None
        assert task.status is WorkflowTaskStatus.COMPLETION_PENDING
        assert outbox.status is OutboxStatus.PENDING
    assert (
        harness.workflow.status_for_process(outbox.payload["processInstanceKey"])
        is RequestStatus.CLOSED_NOT_PROGRESSED
    )
    assert await _event_count(harness, "workflow_close") == 0

    monkeypatch.setattr(SqlAlchemyWorkRepository, "apply_completion", original)
    dispatcher = WorkflowCommandDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch(outbox.id)
    async with harness.sessions() as session:
        request = await session.scalar(select(ServiceRequest))
        recovered = await session.get(WorkflowOutbox, outbox.id)
        assert request is not None
        assert request.status is RequestStatus.CLOSED_NOT_PROGRESSED
        assert recovered is not None and recovered.status is OutboxStatus.SENT
    assert await _event_count(harness, "workflow_close") == 1


async def test_new_command_is_reserved_for_explicit_dispatch_and_is_idempotent(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    listing = await harness.client.get("/api/v1/work-items")
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    original_dispatch = WorkflowCommandDispatcher.dispatch

    async def leave_for_originating_api(
        _dispatcher: WorkflowCommandDispatcher,
        _outbox_id: UUID,
    ) -> bool:
        return False

    monkeypatch.setattr(
        WorkflowCommandDispatcher,
        "dispatch",
        leave_for_originating_api,
    )
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/claim",
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 503

    outbox = await _outbox(harness, "CLAIM_TASK")
    assert outbox.status is OutboxStatus.PENDING
    dispatcher = WorkflowCommandDispatcher(harness.sessions, harness.workflow)
    assert not await dispatcher.dispatch_once()

    monkeypatch.setattr(
        WorkflowCommandDispatcher,
        "dispatch",
        original_dispatch,
    )
    assert await dispatcher.dispatch(outbox.id)
    assert await dispatcher.dispatch(outbox.id)
    assert await _event_count(harness, "workflow_claimed") == 1
