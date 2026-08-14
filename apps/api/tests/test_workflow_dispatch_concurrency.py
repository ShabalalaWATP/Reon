"""API and worker hand-off plus PostgreSQL deadlock recovery contracts."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError

from istari_service.models import OutboxStatus, WorkflowOutbox
from istari_service.work_command_types import WorkCommandType
from istari_service.workflow.errors import (
    WorkflowEngineUnavailable,
    WorkflowRequestRejected,
)
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher

OUTBOX_ID = UUID("00000000-0000-4000-8000-000000000211")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000212")


class StubTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class StubSession:
    def __init__(self, get_values: list[object | None] | None = None) -> None:
        self.get_values = get_values or []

    def __call__(self) -> StubSession:
        return self

    async def __aenter__(self) -> StubSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin(self) -> StubTransaction:
        return StubTransaction()

    async def scalar(self, _statement: object) -> None:
        return None

    async def get(self, _model: type[object], _identity: object) -> object | None:
        return self.get_values.pop(0) if self.get_values else None


def _outbox(status: OutboxStatus, key: str) -> WorkflowOutbox:
    return WorkflowOutbox(
        id=OUTBOX_ID,
        request_id=REQUEST_ID,
        event_type=WorkCommandType.CLAIM_TASK.value,
        payload={},
        idempotency_key=key,
        status=status,
        attempts=1,
        lease_generation=1,
    )


async def test_command_dispatcher_observes_a_competing_lease_result() -> None:
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(
            [
                _outbox(OutboxStatus.PROCESSING, "synthetic-processing"),
                _outbox(OutboxStatus.SENT, "synthetic-sent"),
            ]
        ),
        SimpleNamespace(),
        handoff_poll_attempts=2,
        handoff_poll_seconds=0,
    )

    assert await dispatcher.dispatch(OUTBOX_ID)


async def test_command_dispatcher_fails_closed_for_competing_failure() -> None:
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession([_outbox(OutboxStatus.FAILED, "synthetic-failed")]),
        SimpleNamespace(),
        handoff_poll_attempts=1,
        handoff_poll_seconds=0,
    )

    with pytest.raises(WorkflowRequestRejected):
        await dispatcher.dispatch(OUTBOX_ID)


@pytest.mark.parametrize("status", [None, OutboxStatus.PENDING])
async def test_command_dispatcher_does_not_infer_an_unconfirmed_result(
    status: OutboxStatus | None,
) -> None:
    values = [] if status is None else [_outbox(status, "synthetic-unconfirmed")]
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(values),
        SimpleNamespace(),
        handoff_poll_attempts=1,
        handoff_poll_seconds=0,
    )

    assert not await dispatcher.dispatch(OUTBOX_ID)


async def test_command_dispatcher_bounds_a_still_processing_handoff() -> None:
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession([_outbox(OutboxStatus.PROCESSING, "synthetic-bounded")]),
        SimpleNamespace(),
        handoff_poll_attempts=1,
        handoff_poll_seconds=0,
    )

    assert not await dispatcher.dispatch(OUTBOX_ID)


class SyntheticPostgresError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("synthetic database error")
        self.sqlstate = sqlstate


async def test_command_dispatcher_retries_one_postgres_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(), SimpleNamespace(), database_retry_attempts=2
    )
    calls = 0

    async def run(_outbox_id: UUID) -> tuple[bool, None]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise DBAPIError("synthetic", {}, SyntheticPostgresError("40P01"))
        return True, None

    monkeypatch.setattr(dispatcher, "_run", run)

    assert await dispatcher.dispatch(OUTBOX_ID)
    assert calls == 2


@pytest.mark.parametrize("sqlstate", ["40P01", "23505"])
async def test_command_dispatcher_bounds_database_failures(
    monkeypatch: pytest.MonkeyPatch,
    sqlstate: str,
) -> None:
    dispatcher = WorkflowCommandDispatcher(  # type: ignore[arg-type]
        StubSession(), SimpleNamespace(), database_retry_attempts=1
    )
    failure = DBAPIError("synthetic", {}, SyntheticPostgresError(sqlstate))

    async def fail(_outbox_id: UUID) -> tuple[bool, None]:
        raise failure

    monkeypatch.setattr(dispatcher, "_run", fail)

    expected = WorkflowEngineUnavailable if sqlstate == "40P01" else DBAPIError
    with pytest.raises(expected):
        await dispatcher.dispatch(OUTBOX_ID)
