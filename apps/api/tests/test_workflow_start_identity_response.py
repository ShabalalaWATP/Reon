"""Fresh Camunda starts must preserve the immutable requested identity."""

from typing import Any

import httpx
import pytest

from mist_service.workflow.errors import WorkflowContractError
from mist_service.workflow.types import StartProcessCommand
from test_workflow_camunda_support import (
    REQUEST_ID,
    REQUESTER_ID,
    creation_result,
    running_engine,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_update",
    [
        {"processDefinitionId": "wrong_definition"},
        {"processDefinitionVersion": 3},
    ],
)
async def test_process_start_rejects_identity_outside_the_requested_pin(
    response_update: dict[str, Any],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=creation_result(**response_update))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError):
            await engine.start_process(
                StartProcessCommand(
                    "service_request",
                    REQUEST_ID,
                    REQUESTER_ID,
                    process_definition_version=2,
                )
            )
