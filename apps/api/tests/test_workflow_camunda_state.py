"""Exact process-state lookup tests for terminal completion recovery."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import istari_service.workflow.camunda as camunda_module
from istari_service.workflow.errors import (
    AmbiguousWorkflowProcess,
    WorkflowContractError,
    WorkflowEngineUnavailable,
)
from istari_service.workflow.types import (
    ProcessStateQuery,
    WorkflowProcessSnapshot,
    WorkflowProcessState,
)
from test_workflow_camunda_support import (
    PROCESS_INSTANCE_KEY,
    page,
    problem,
    process_result,
    request_json,
    running_engine,
)


@pytest.mark.parametrize("state", list(WorkflowProcessState))
@pytest.mark.asyncio
async def test_process_state_lookup_uses_exact_key_and_maps_state(
    state: WorkflowProcessState,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=page(process_result(state=state.value)))

    async with running_engine(handler) as engine:
        snapshot = await engine.find_process_state(
            ProcessStateQuery(PROCESS_INSTANCE_KEY)
        )

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v2/process-instances/search"
    assert request_json(requests[0]) == {
        "filter": {"processInstanceKey": PROCESS_INSTANCE_KEY},
        "page": {"limit": 2},
    }
    assert snapshot == WorkflowProcessSnapshot(PROCESS_INSTANCE_KEY, state)


@pytest.mark.asyncio
async def test_process_state_lookup_returns_none_when_key_is_absent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page())

    async with running_engine(handler) as engine:
        snapshot = await engine.find_process_state(
            ProcessStateQuery(PROCESS_INSTANCE_KEY)
        )

    assert snapshot is None


@pytest.mark.asyncio
async def test_process_state_lookup_rejects_duplicate_exact_keys() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=page(process_result(), process_result()),
        )

    async with running_engine(handler) as engine:
        with pytest.raises(AmbiguousWorkflowProcess, match="not unique"):
            await engine.find_process_state(ProcessStateQuery(PROCESS_INSTANCE_KEY))


@pytest.mark.asyncio
async def test_process_state_lookup_rejects_mismatched_response_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=page(process_result(processInstanceKey="2251799813685299")),
        )

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="different process key"):
            await engine.find_process_state(ProcessStateQuery(PROCESS_INSTANCE_KEY))


@pytest.mark.asyncio
async def test_process_state_lookup_rejects_invalid_sdk_key_before_io() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="process key"):
            await engine.find_process_state(ProcessStateQuery("not-numeric"))
    assert calls == 0


@pytest.mark.asyncio
async def test_process_state_lookup_rejects_unknown_mapped_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_state(_value: str) -> WorkflowProcessState:
        raise ValueError("Synthetic unknown state")

    monkeypatch.setattr(camunda_module, "WorkflowProcessState", reject_state)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page(process_result()))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="invalid state"):
            await engine.find_process_state(ProcessStateQuery(PROCESS_INSTANCE_KEY))


@pytest.mark.asyncio
async def test_process_state_lookup_translates_engine_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=problem(503, "Unavailable"))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowEngineUnavailable, match="find_process_state"):
            await engine.find_process_state(ProcessStateQuery(PROCESS_INSTANCE_KEY))


@pytest.mark.parametrize(
    ("factory", "error"),
    [
        (lambda: ProcessStateQuery(" "), ValueError),
        (
            lambda: WorkflowProcessSnapshot("", WorkflowProcessState.ACTIVE),
            ValueError,
        ),
        (lambda: WorkflowProcessSnapshot("process", "ACTIVE"), TypeError),
    ],
)
def test_process_state_values_reject_invalid_contracts(
    factory: Any,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        factory()
