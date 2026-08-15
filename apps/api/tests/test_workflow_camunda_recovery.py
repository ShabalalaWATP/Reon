"""Bounded process-start conflict recovery through Camunda's search index."""

from __future__ import annotations

import httpx
import pytest

from mist_service.workflow.camunda import CamundaWorkflowEngine
from mist_service.workflow.errors import (
    AmbiguousWorkflowProcess,
    WorkflowConflict,
    WorkflowProcessNotVisible,
)
from mist_service.workflow.types import StartProcessCommand
from test_workflow_camunda_support import (
    PROCESS_INSTANCE_KEY,
    REQUEST_ID,
    REQUESTER_ID,
    page,
    problem,
    process_result,
    running_engine,
)


@pytest.mark.asyncio
async def test_conflict_recovery_waits_for_one_unique_process() -> None:
    search_count = 0
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal search_count
        if request.url.path == "/v2/process-instances":
            return httpx.Response(409, json=problem(409, "Conflict"))
        search_count += 1
        if search_count == 1:
            return httpx.Response(200, json=page())
        return httpx.Response(200, json=page(process_result()))

    async with running_engine(
        handler,
        recovery_attempts=3,
        recovery_delay=0.2,
        sleep=record_sleep,
    ) as engine:
        started = await engine.start_process(
            StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
        )

    assert started.process_instance_key == PROCESS_INSTANCE_KEY
    assert search_count == 2
    assert sleeps == [0.2]


@pytest.mark.asyncio
async def test_conflict_recovery_succeeds_without_sleep_when_already_visible() -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/process-instances":
            return httpx.Response(409, json=problem(409, "Conflict"))
        return httpx.Response(200, json=page(process_result()))

    async with running_engine(handler, sleep=record_sleep) as engine:
        started = await engine.start_process(
            StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
        )

    assert started.process_instance_key == PROCESS_INSTANCE_KEY
    assert sleeps == []


@pytest.mark.asyncio
async def test_conflict_recovery_rejects_ambiguous_processes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/process-instances":
            return httpx.Response(409, json=problem(409, "Conflict"))
        return httpx.Response(
            200,
            json=page(
                process_result(),
                process_result(
                    processInstanceKey="2251799813685299",
                    rootProcessInstanceKey="2251799813685299",
                ),
            ),
        )

    async with running_engine(handler) as engine:
        with pytest.raises(AmbiguousWorkflowProcess, match="multiple processes"):
            await engine.start_process(
                StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
            )


@pytest.mark.asyncio
async def test_conflict_recovery_exhausts_finite_attempts() -> None:
    searches = 0
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal searches
        if request.url.path == "/v2/process-instances":
            return httpx.Response(409, json=problem(409, "Conflict"))
        searches += 1
        return httpx.Response(200, json=page())

    async with running_engine(
        handler,
        recovery_attempts=3,
        recovery_delay=0.1,
        sleep=record_sleep,
    ) as engine:
        with pytest.raises(WorkflowProcessNotVisible) as caught:
            await engine.start_process(
                StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
            )

    assert searches == 3
    assert sleeps == [0.1, 0.1]
    assert isinstance(caught.value.__cause__, WorkflowConflict)


@pytest.mark.parametrize(
    ("attempts", "delay"),
    [
        (0, 0.1),
        (21, 0.1),
        (1, -0.1),
        (1, 5.1),
    ],
)
def test_recovery_settings_are_strictly_bounded(
    attempts: int,
    delay: float,
) -> None:
    with pytest.raises(ValueError):
        CamundaWorkflowEngine(
            object(),  # type: ignore[arg-type]
            start_recovery_attempts=attempts,
            start_recovery_delay_seconds=delay,
        )
