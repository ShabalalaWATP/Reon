"""Camunda V2 process-cancellation wire contract."""

from __future__ import annotations

import httpx
import pytest

from istari_service.workflow.errors import WorkflowContractError
from istari_service.workflow.types import CancelProcessCommand
from test_workflow_camunda_support import (
    PROCESS_INSTANCE_KEY,
    request_json,
    running_engine,
)


@pytest.mark.asyncio
async def test_cancellation_uses_the_official_v2_process_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    async with running_engine(handler) as engine:
        await engine.cancel_process(CancelProcessCommand(PROCESS_INSTANCE_KEY))

    assert requests[0].method == "POST"
    assert requests[0].url.path == (
        f"/v2/process-instances/{PROCESS_INSTANCE_KEY}/cancellation"
    )
    assert request_json(requests[0]) == {}


@pytest.mark.asyncio
async def test_cancellation_rejects_an_invalid_process_key_locally() -> None:
    async with running_engine(lambda _request: httpx.Response(204)) as engine:
        with pytest.raises(WorkflowContractError, match="process instance key"):
            await engine.cancel_process(CancelProcessCommand("not-a-camunda-key"))
