"""Direct intent-boundary tests independent of SQLAlchemy greenlet tracing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from istari_service.domain import Actor, RequestRecord, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import (
    ProductMode,
    RequestStatus,
    UserRole,
    WorkflowTaskStatus,
)
from istari_service.repositories.work_intents import (
    PENDING_MESSAGE,
    prepare_claim_intent,
    prepare_completion_intent,
)
from istari_service.schemas.work import CloseRequest


class IntentSession:
    def __init__(self, task: object | None, request: object | None) -> None:
        self._rows = [task, request]
        self.added: list[object] = []
        self.flushes = 0

    async def scalar(self, _statement: object) -> object | None:
        return self._rows.pop(0) if self._rows else True

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1


def _state() -> tuple[Actor, WorkRecord, Any, Any]:
    actor = Actor(
        id=uuid4(),
        username="triage@example.test",
        display_name="Synthetic Triage",
        role=UserRole.INTAKE_TRIAGE,
        scope="Shared queue",
        organisation_unit_ids=frozenset({uuid4()}),
    )
    request = SimpleNamespace(
        id=uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.TRIAGE_REVIEW,
        assigned_delivery_team=None,
        assigned_specialist_id=None,
        product_mode=ProductMode.LEGACY,
        version=1,
        workflow_error=None,
    )
    task = SimpleNamespace(
        id=uuid4(),
        task_key="task-1",
        element_id="triage-review",
        status=WorkflowTaskStatus.OPEN,
        assignee_user_id=None,
        candidate_role=UserRole.INTAKE_TRIAGE,
        expected_status=RequestStatus.TRIAGE_REVIEW,
    )
    record = RequestRecord(
        id=request.id,
        requester_id=request.requester_id,
        status=request.status,
        assigned_delivery_team=None,
        assigned_specialist_id=None,
        version=1,
    )
    work = WorkRecord(
        id=task.id,
        request=record,
        engine_task_key=task.task_key,
        process_instance_key="process-1",
        element_id=task.element_id,
        task_status=task.status,
        assignee_id=None,
        completed_at=None,
    )
    return actor, work, task, request


async def test_prepare_claim_records_a_validated_durable_intent() -> None:
    actor, work, task, request = _state()
    session = IntentSession(task, request)

    outbox_id = await prepare_claim_intent(session, work, actor)  # type: ignore[arg-type]

    outbox = session.added[0]
    assert outbox.id == outbox_id
    assert outbox.event_type == "CLAIM_TASK"
    assert task.status is WorkflowTaskStatus.CLAIM_PENDING
    assert task.assignee_user_id == actor.id
    assert request.workflow_error == PENDING_MESSAGE
    assert session.flushes == 1
    assert outbox.available_at >= datetime.now(UTC) + timedelta(seconds=4)


async def test_prepare_claim_rejects_changed_or_ineligible_state() -> None:
    actor, work, task, request = _state()
    task.status = WorkflowTaskStatus.CLAIMED

    with pytest.raises(InvalidAction):
        await prepare_claim_intent(  # type: ignore[arg-type]
            IntentSession(task, request), work, actor
        )

    with pytest.raises(InvalidAction):
        await prepare_claim_intent(  # type: ignore[arg-type]
            IntentSession(None, request), work, actor
        )


async def test_prepare_completion_records_and_rejects_intents() -> None:
    actor, work, task, request = _state()
    task.status = WorkflowTaskStatus.CLAIMED
    task.assignee_user_id = actor.id
    claimed = WorkRecord(
        id=work.id,
        request=work.request,
        engine_task_key=work.engine_task_key,
        process_instance_key=work.process_instance_key,
        element_id=work.element_id,
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=actor.id,
        completed_at=None,
    )
    payload = CloseRequest(action="close", reason="Synthetic closure reason")
    session = IntentSession(task, request)

    outbox_id = await prepare_completion_intent(  # type: ignore[arg-type]
        session, claimed, actor, payload
    )

    outbox = session.added[0]
    assert outbox.id == outbox_id
    assert outbox.event_type == "COMPLETE_TASK"
    assert outbox.payload["completion"]["action"] == "close"
    assert task.status is WorkflowTaskStatus.COMPLETION_PENDING
    assert request.workflow_error == PENDING_MESSAGE

    task.status = WorkflowTaskStatus.OPEN
    with pytest.raises(InvalidAction):
        await prepare_completion_intent(  # type: ignore[arg-type]
            IntentSession(task, request), claimed, actor, payload
        )
