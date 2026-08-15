"""Durable command-result projections across retry and recovery branches."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

import mist_service.workflow_command_results as results_module
from mist_service.domain import RequestRecord, WorkRecord
from mist_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowOutbox,
    WorkflowTaskStatus,
)
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.workflow.types import WorkflowTask, WorkflowTaskState
from mist_service.workflow_command_results import (
    RETRY_EXHAUSTED_MESSAGE,
    RETRY_MESSAGE,
    SUPPORT_MESSAGE,
    mark_support_failure,
    project_competing_claim,
    schedule_retry,
    stored_work_id,
)


class ResultSession:
    def __init__(
        self,
        *,
        request: object | None = None,
        task: object | None = None,
        user: object | None = None,
        membership: bool = True,
    ) -> None:
        self.request = request
        self.task = task
        self.user = user
        self.membership = membership
        self.scalar_statements: list[object] = []

    async def get(self, model: type[object], _identity: object) -> object | None:
        if model is ServiceRequest:
            return self.request
        if model is StoredWorkflowTask:
            return self.task
        if model is User:
            return self.user
        return None

    async def scalar(self, statement: object) -> object | None:
        self.scalar_statements.append(statement)
        if len(self.scalar_statements) == 1:
            return self.user
        return uuid4() if self.membership else None

    async def scalars(self, _statement: object) -> list[object]:
        return [uuid4()] if self.membership else []


def _outbox(*, attempts: int = 1) -> WorkflowOutbox:
    return WorkflowOutbox(
        request_id=uuid4(),
        event_type="CLAIM_TASK",
        payload={},
        idempotency_key=f"synthetic-{uuid4()}",
        status=OutboxStatus.PROCESSING,
        attempts=attempts,
    )


@pytest.mark.parametrize("exhausted", [False, True])
async def test_schedule_retry_projects_pending_and_exhausted_states(
    exhausted: bool,
) -> None:
    request = SimpleNamespace(workflow_error=None)
    task = SimpleNamespace(status=WorkflowTaskStatus.CLAIM_PENDING)
    outbox = _outbox(attempts=2 if exhausted else 1)
    session = ResultSession(request=request, task=task)

    await schedule_retry(  # type: ignore[arg-type]
        session, outbox, uuid4(), max_attempts=2
    )

    expected = RETRY_EXHAUSTED_MESSAGE if exhausted else RETRY_MESSAGE
    assert outbox.status is (OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING)
    assert outbox.last_error == expected
    assert request.workflow_error == (SUPPORT_MESSAGE if exhausted else RETRY_MESSAGE)
    expected_task = (
        WorkflowTaskStatus.ERROR if exhausted else WorkflowTaskStatus.CLAIM_PENDING
    )
    assert task.status is expected_task


async def test_retry_and_support_projection_tolerate_missing_rows() -> None:
    outbox = _outbox()
    session = ResultSession()
    await schedule_retry(  # type: ignore[arg-type]
        session, outbox, uuid4(), max_attempts=3
    )
    await mark_support_failure(session, outbox, None)  # type: ignore[arg-type]
    assert outbox.status is OutboxStatus.FAILED
    assert outbox.last_error == SUPPORT_MESSAGE

    await mark_support_failure(  # type: ignore[arg-type]
        ResultSession(request=SimpleNamespace(workflow_error=None)),
        _outbox(),
        uuid4(),
    )


def _competing_state() -> tuple[Any, Any, Any, WorkRecord, WorkflowTask]:
    user_id = uuid4()
    request_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        username="admin7",
        display_name="Synthetic Colleague",
        role=UserRole.INTAKE_TRIAGE,
        scope="Shared queue",
        is_active=True,
    )
    request = SimpleNamespace(
        id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.TRIAGE_REVIEW,
        assigned_delivery_team=None,
        assigned_specialist_id=None,
        workflow_error=RETRY_MESSAGE,
    )
    task = SimpleNamespace(
        id=uuid4(),
        task_key="task-1",
        status=WorkflowTaskStatus.CLAIM_PENDING,
        candidate_role=UserRole.INTAKE_TRIAGE,
        assignee_user_id=uuid4(),
        claimed_at=None,
    )
    record = WorkRecord(
        id=task.id,
        request=RequestRecord(
            id=request.id,
            requester_id=request.requester_id,
            status=request.status,
            assigned_delivery_team=None,
            assigned_specialist_id=None,
            version=1,
        ),
        engine_task_key=task.task_key,
        process_instance_key="process-1",
        element_id="triage-review",
        task_status=WorkflowTaskStatus.CLAIM_PENDING,
        assignee_id=task.assignee_user_id,
        completed_at=None,
    )
    engine_task = WorkflowTask(
        task_key=task.task_key,
        process_instance_key="process-1",
        element_id="triage-review",
        state=WorkflowTaskState.CREATED,
        assignee=str(user.id),
    )
    return user, request, task, record, engine_task


async def test_competing_claim_is_projected_only_for_valid_assignee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, request, task, work, engine_task = _competing_state()
    events: list[dict[str, object]] = []

    async def append_event(_session: object, **values: object) -> None:
        events.append(values)

    monkeypatch.setattr(results_module, "append_request_event", append_event)
    outbox = _outbox()
    valid_session = ResultSession(request=request, task=task, user=user)
    projected = await project_competing_claim(  # type: ignore[arg-type]
        valid_session,
        outbox,
        work,
        engine_task,
    )
    assert projected
    assert task.status is WorkflowTaskStatus.CLAIMED
    assert task.assignee_user_id == user.id
    assert request.workflow_error is None
    assert outbox.status is OutboxStatus.FAILED
    assert len(events) == 1
    assert all(
        statement._for_update_arg is not None  # type: ignore[attr-defined]
        for statement in valid_session.scalar_statements
    )

    task.status = WorkflowTaskStatus.CLAIM_PENDING
    task.assignee_user_id = uuid4()
    request.workflow_error = RETRY_MESSAGE
    revoked = await project_competing_claim(  # type: ignore[arg-type]
        ResultSession(request=request, task=task, user=user, membership=False),
        _outbox(),
        work,
        engine_task,
    )
    assert not revoked
    assert task.status is WorkflowTaskStatus.ERROR

    invalid = WorkflowTask(
        task_key=engine_task.task_key,
        process_instance_key=engine_task.process_instance_key,
        element_id=engine_task.element_id,
        state=engine_task.state,
        assignee="not-a-uuid",
    )
    assert not await project_competing_claim(  # type: ignore[arg-type]
        ResultSession(request=request, task=task), _outbox(), work, invalid
    )

    user.is_active = False
    assert not await project_competing_claim(  # type: ignore[arg-type]
        ResultSession(request=request, task=task, user=user),
        _outbox(),
        work,
        engine_task,
    )


def test_stored_work_id_is_fail_closed() -> None:
    work_id = uuid4()
    assert stored_work_id({"workId": str(work_id)}) == work_id
    assert stored_work_id({}) is None
    assert stored_work_id({"workId": "not-a-uuid"}) is None
