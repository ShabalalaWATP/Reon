"""Bounded workflow maintenance loop branch coverage."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, cast

import pytest

import mist_service.workflow_maintenance as maintenance_module
from mist_service.workflow_maintenance import (
    WorkflowMaintenanceHealth,
    run_workflow_maintenance,
)


class LoopDispatcher:
    def __init__(self, result: bool, stop: asyncio.Event | None = None) -> None:
        self.result = result
        self.stop = stop
        self.calls = 0

    async def dispatch_once(self) -> bool:
        self.calls += 1
        if self.stop is not None:
            self.stop.set()
        return self.result


class LoopReconciler:
    def __init__(self, result: bool, stop: asyncio.Event | None = None) -> None:
        self.result = result
        self.stop = stop
        self.calls = 0

    async def reconcile_once(self) -> bool:
        self.calls += 1
        if self.stop is not None:
            self.stop.set()
        return self.result


class FlakyDispatcher:
    def __init__(self, stop: asyncio.Event) -> None:
        self.stop = stop
        self.calls = 0

    async def dispatch_once(self) -> bool:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("synthetic transient maintenance failure")
        self.stop.set()
        return False


@pytest.mark.asyncio
async def test_maintenance_returns_immediately_when_stopped() -> None:
    stop = asyncio.Event()
    stop.set()
    dispatcher = LoopDispatcher(False)
    reconciler = LoopReconciler(False)
    await run_workflow_maintenance(cast(Any, dispatcher), cast(Any, reconciler), stop)
    assert dispatcher.calls == reconciler.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("worked", "reconciled"), [(True, False), (False, True)])
async def test_maintenance_continues_immediately_after_work(
    worked: bool,
    reconciled: bool,
) -> None:
    stop = asyncio.Event()
    dispatcher = LoopDispatcher(worked, stop if worked else None)
    reconciler = LoopReconciler(reconciled, stop if reconciled else None)
    await run_workflow_maintenance(cast(Any, dispatcher), cast(Any, reconciler), stop)
    assert dispatcher.calls == reconciler.calls == 1


@pytest.mark.asyncio
async def test_maintenance_waits_for_stop_when_idle() -> None:
    stop = asyncio.Event()
    await run_workflow_maintenance(
        cast(Any, LoopDispatcher(False)),
        cast(Any, LoopReconciler(False, stop)),
        stop,
    )


@pytest.mark.asyncio
async def test_maintenance_retries_after_idle_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = asyncio.Event()

    async def timeout_once(
        awaitable: Coroutine[Any, Any, bool], **options: float
    ) -> None:
        assert options == {"timeout": 0.25}
        awaitable.close()
        stop.set()
        raise TimeoutError

    monkeypatch.setattr(maintenance_module.asyncio, "wait_for", timeout_once)
    await run_workflow_maintenance(
        cast(Any, LoopDispatcher(False)),
        cast(Any, LoopReconciler(False)),
        stop,
        interval_seconds=0.25,
    )


@pytest.mark.asyncio
async def test_maintenance_recovers_after_an_unexpected_iteration_failure() -> None:
    stop = asyncio.Event()
    dispatcher = FlakyDispatcher(stop)
    health = WorkflowMaintenanceHealth()
    await run_workflow_maintenance(
        cast(Any, dispatcher),
        cast(Any, LoopReconciler(False)),
        stop,
        interval_seconds=0,
        health=health,
    )
    assert dispatcher.calls == 2
    assert health.consecutive_failures == 0
    assert health.last_failure_at is not None
    assert health.last_success_at is not None
