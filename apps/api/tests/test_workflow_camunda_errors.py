"""Failure translation and defensive response validation for Camunda V2."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import mist_service.workflow.camunda as camunda_module
from mist_service.workflow.camunda import CamundaWorkflowEngine
from mist_service.workflow.errors import (
    InvalidWorkflowTransition,
    WorkflowConflict,
    WorkflowContractError,
    WorkflowEngineUnavailable,
    WorkflowRequestRejected,
    WorkflowTaskNotFound,
)
from mist_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    CompleteTaskCommand,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowAction,
)
from test_workflow_camunda_support import (
    ASSIGNEE_ID,
    PROCESS_INSTANCE_KEY,
    REQUEST_ID,
    REQUESTER_ID,
    TASK_KEY,
    TENANT_ID,
    creation_result,
    page,
    problem,
    process_result,
    running_engine,
)

HTTP_ERRORS = (
    (400, WorkflowRequestRejected),
    (404, WorkflowTaskNotFound),
    (409, WorkflowConflict),
    (429, WorkflowEngineUnavailable),
    (500, WorkflowEngineUnavailable),
    (503, WorkflowEngineUnavailable),
)


@pytest.mark.parametrize(("status", "expected_error"), HTTP_ERRORS)
@pytest.mark.asyncio
async def test_sdk_http_errors_are_translated_by_semantics(
    status: int,
    expected_error: type[Exception],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=problem(status))

    async with running_engine(handler) as engine:
        with pytest.raises(expected_error) as caught:
            await engine.claim_task(ClaimTaskCommand(TASK_KEY, ASSIGNEE_ID))

    if isinstance(caught.value, WorkflowRequestRejected):
        assert caught.value.operation == "claim_task"
        assert caught.value.status_code == status


@pytest.mark.asyncio
async def test_complete_not_found_preserves_operation_context() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json=problem(404, "Not found"))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowTaskNotFound) as caught:
            await engine.complete_task(
                CompleteTaskCommand(
                    TASK_KEY,
                    PROCESS_INSTANCE_KEY,
                    "intake_review",
                    WorkflowAction.PROGRESS,
                )
            )
    assert caught.value.operation == "complete_task"
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_transport_errors_are_unavailable_and_status_remains_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Synthetic connection failure", request=request)

    async with running_engine(handler) as engine:
        assert await engine.is_reachable() is False
        with pytest.raises(WorkflowEngineUnavailable, match="claim_task"):
            await engine.claim_task(ClaimTaskCommand(TASK_KEY, ASSIGNEE_ID))


@pytest.mark.asyncio
async def test_status_maps_sdk_failure_to_false() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=problem(503, "Unavailable"))

    async with running_engine(handler) as engine:
        assert await engine.is_reachable() is False


@pytest.mark.parametrize(
    "exception",
    [KeyError("missing"), TypeError("wrong type"), ValueError("bad value")],
)
@pytest.mark.asyncio
async def test_parser_failures_become_contract_errors(exception: Exception) -> None:
    async def failing_request() -> None:
        raise exception

    with pytest.raises(WorkflowContractError, match="decode_result"):
        await CamundaWorkflowEngine._call("decode_result", failing_request())


@pytest.mark.asyncio
async def test_malformed_sdk_success_response_becomes_contract_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="invalid response"):
            await engine.start_process(
                StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
            )


@pytest.mark.parametrize("business_id", [None, "different-business-id"])
@pytest.mark.asyncio
async def test_start_rejects_missing_or_changed_business_id(
    business_id: str | None,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=creation_result(businessId=business_id))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="business ID"):
            await engine.start_process(
                StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
            )


PROCESS_MISMATCHES = (
    (
        StartedProcessQuery("service_request", REQUEST_ID),
        {"businessId": "different"},
        "business ID",
    ),
    (
        StartedProcessQuery("service_request", REQUEST_ID),
        {"processDefinitionId": "different"},
        "different definition",
    ),
    (
        StartedProcessQuery("service_request", REQUEST_ID, 1),
        {"processDefinitionVersion": 2},
        "definition version",
    ),
    (
        StartedProcessQuery("service_request", REQUEST_ID, tenant_id=TENANT_ID),
        {"tenantId": "tenant-b"},
        "different tenant",
    ),
    (
        StartedProcessQuery("service_request", REQUEST_ID),
        {"parentProcessInstanceKey": "2251799813685299"},
        "child process",
    ),
)


@pytest.mark.parametrize(("query", "updates", "message"), PROCESS_MISMATCHES)
@pytest.mark.asyncio
async def test_process_lookup_rejects_mismatched_or_child_results(
    query: StartedProcessQuery,
    updates: dict[str, Any],
    message: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page(process_result(**updates)))

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match=message):
            await engine.find_started_process(query)


@pytest.mark.parametrize(
    "command",
    [
        StartProcessCommand("bad id", REQUEST_ID, REQUESTER_ID),
        StartProcessCommand(
            "service_request", REQUEST_ID, REQUESTER_ID, tenant_id="bad tenant"
        ),
    ],
)
@pytest.mark.asyncio
async def test_invalid_sdk_process_identity_is_rejected_before_io(
    command: StartProcessCommand,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="process identity"):
            await engine.start_process(command)
    assert calls == 0


@pytest.mark.parametrize("operation", ["claim", "complete"])
@pytest.mark.asyncio
async def test_invalid_sdk_task_key_is_rejected_before_io(operation: str) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with running_engine(handler) as engine:
        with pytest.raises(WorkflowContractError, match="task key"):
            if operation == "claim":
                await engine.claim_task(ClaimTaskCommand("not-numeric", ASSIGNEE_ID))
            else:
                await engine.complete_task(
                    CompleteTaskCommand(
                        "not-numeric",
                        PROCESS_INSTANCE_KEY,
                        "intake_review",
                        WorkflowAction.PROGRESS,
                    )
                )
    assert calls == 0


@pytest.mark.asyncio
async def test_invalid_task_element_contract_is_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_element(value: str) -> str:
        raise ValueError(value)

    monkeypatch.setattr(camunda_module, "ElementId", reject_element)
    async with running_engine(lambda _request: httpx.Response(500)) as engine:
        with pytest.raises(WorkflowContractError, match="task element"):
            await engine.search_active_tasks(
                ActiveTaskQuery(PROCESS_INSTANCE_KEY, "intake_review")
            )


def test_invalid_mapped_task_state_is_a_contract_error() -> None:
    malformed = SimpleNamespace(
        state=SimpleNamespace(value="UNKNOWN"),
        user_task_key=TASK_KEY,
        process_instance_key=PROCESS_INSTANCE_KEY,
        element_id="intake_review",
        assignee=None,
    )
    with pytest.raises(WorkflowContractError, match="user-task result"):
        CamundaWorkflowEngine._map_task(malformed)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_adapter_rejects_action_that_does_not_match_element() -> None:
    async with running_engine(lambda _request: httpx.Response(204)) as engine:
        with pytest.raises(InvalidWorkflowTransition):
            await engine.complete_task(
                CompleteTaskCommand(
                    TASK_KEY,
                    PROCESS_INSTANCE_KEY,
                    "intake_review",
                    WorkflowAction.RELEASE,
                )
            )
