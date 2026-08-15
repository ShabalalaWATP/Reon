"""Wire-contract tests for commands sent through the official Camunda SDK."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from mist_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    CompleteTaskCommand,
    DeliveryTeamId,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowAction,
    WorkflowTaskState,
)
from test_workflow_camunda_support import (
    ASSIGNEE_ID,
    PROCESS_DEFINITION_KEY,
    PROCESS_INSTANCE_KEY,
    REQUEST_ID,
    REQUESTER_ID,
    SPECIALIST_ID,
    TASK_KEY,
    TENANT_ID,
    creation_result,
    page,
    process_result,
    request_json,
    running_engine,
    task_result,
)


@pytest.mark.asyncio
async def test_status_and_default_process_start_use_v2_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v2/status":
            return httpx.Response(204)
        return httpx.Response(200, json=creation_result())

    async with running_engine(handler) as engine:
        assert await engine.is_reachable() is True
        started = await engine.start_process(
            StartProcessCommand("service_request", REQUEST_ID, REQUESTER_ID)
        )

    assert [(item.method, item.url.path) for item in requests] == [
        ("GET", "/v2/status"),
        ("POST", "/v2/process-instances"),
    ]
    assert request_json(requests[1]) == {
        "processDefinitionId": "service_request",
        "processDefinitionVersion": -1,
        "variables": {
            "requestId": str(REQUEST_ID),
            "requesterId": str(REQUESTER_ID),
        },
        "businessId": str(REQUEST_ID),
    }
    assert started.process_instance_key == PROCESS_INSTANCE_KEY
    assert started.process_definition_key == PROCESS_DEFINITION_KEY
    assert started.process_definition_version == 1
    assert started.business_id == str(REQUEST_ID)


@pytest.mark.asyncio
async def test_explicit_version_and_tenant_are_sent_only_when_selected() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=creation_result(
                processDefinitionVersion=2,
                tenantId=TENANT_ID,
            ),
        )

    async with running_engine(handler) as engine:
        started = await engine.start_process(
            StartProcessCommand(
                "service_request",
                REQUEST_ID,
                REQUESTER_ID,
                process_definition_version=2,
                tenant_id=TENANT_ID,
            )
        )

    assert request_json(requests[0]) == {
        "processDefinitionId": "service_request",
        "processDefinitionVersion": 2,
        "variables": {
            "requestId": str(REQUEST_ID),
            "requesterId": str(REQUESTER_ID),
        },
        "tenantId": TENANT_ID,
        "businessId": str(REQUEST_ID),
    }
    assert started.process_definition_version == 2


@pytest.mark.asyncio
async def test_process_lookup_uses_exact_identity_and_bounded_page() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request_json(request))
        if len(bodies) == 1:
            return httpx.Response(
                200,
                json=page(
                    process_result(
                        processDefinitionVersion=2,
                        tenantId=TENANT_ID,
                    )
                ),
            )
        return httpx.Response(200, json=page())

    async with running_engine(handler) as engine:
        found = await engine.find_started_process(
            StartedProcessQuery(
                "service_request",
                REQUEST_ID,
                process_definition_version=2,
                tenant_id=TENANT_ID,
            )
        )
        missing = await engine.find_started_process(
            StartedProcessQuery("service_request", REQUEST_ID)
        )

    assert found is not None
    assert found.process_instance_key == PROCESS_INSTANCE_KEY
    assert missing is None
    assert bodies == [
        {
            "filter": {
                "processDefinitionId": "service_request",
                "processDefinitionVersion": 2,
                "tenantId": TENANT_ID,
                "businessId": str(REQUEST_ID),
            },
            "page": {"limit": 2},
        },
        {
            "filter": {
                "processDefinitionId": "service_request",
                "businessId": str(REQUEST_ID),
            },
            "page": {"limit": 2},
        },
    ]


@pytest.mark.asyncio
async def test_task_search_maps_exact_created_tasks() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=page(task_result(assignee=str(ASSIGNEE_ID))),
        )

    async with running_engine(handler) as engine:
        tasks = await engine.search_active_tasks(
            ActiveTaskQuery(PROCESS_INSTANCE_KEY, "intake_review")
        )

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v2/user-tasks/search"
    assert request_json(requests[0]) == {
        "filter": {
            "state": "CREATED",
            "processInstanceKey": PROCESS_INSTANCE_KEY,
            "elementId": "intake_review",
        },
        "page": {"limit": 2},
    }
    assert len(tasks) == 1
    assert tasks[0].task_key == TASK_KEY
    assert tasks[0].process_instance_key == PROCESS_INSTANCE_KEY
    assert tasks[0].element_id == "intake_review"
    assert tasks[0].state is WorkflowTaskState.CREATED
    assert tasks[0].assignee == str(ASSIGNEE_ID)


@pytest.mark.asyncio
async def test_task_search_omits_unspecified_element_filter() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=page())

    async with running_engine(handler) as engine:
        assert (
            await engine.search_active_tasks(ActiveTaskQuery(PROCESS_INSTANCE_KEY))
            == ()
        )

    assert request_json(requests[0]) == {
        "filter": {
            "state": "CREATED",
            "processInstanceKey": PROCESS_INSTANCE_KEY,
        },
        "page": {"limit": 2},
    }


@pytest.mark.asyncio
async def test_claim_sends_non_overriding_assignment() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    async with running_engine(handler) as engine:
        await engine.claim_task(ClaimTaskCommand(TASK_KEY, ASSIGNEE_ID))

    assert requests[0].method == "POST"
    assert requests[0].url.path == f"/v2/user-tasks/{TASK_KEY}/assignment"
    assert request_json(requests[0]) == {
        "assignee": str(ASSIGNEE_ID),
        "allowOverride": False,
        "action": "claim",
    }


COMPLETIONS = (
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "intake_review",
            WorkflowAction.PROGRESS,
        ),
        {"intakeDecision": "progress"},
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "allocation_review",
            WorkflowAction.ALLOCATE,
            delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A,
        ),
        {
            "allocationDecision": "allocate",
            "assignedDeliveryTeamId": "DELIVERY_TEAM_A",
        },
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "delivery_planning",
            WorkflowAction.ASSIGN,
            specialist_id=SPECIALIST_ID,
        ),
        {
            "planningDecision": "assign",
            "assignedSpecialistId": str(SPECIALIST_ID),
        },
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "delivery_work",
            WorkflowAction.SUBMIT,
        ),
        {"deliveryDecision": "submit"},
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "delivery_work",
            WorkflowAction.REQUEST_CLARIFICATION,
        ),
        {"deliveryDecision": "request_clarification"},
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "customer_clarification_response",
            WorkflowAction.PROVIDE_CLARIFICATION,
        ),
        {"clarificationDecision": "provide_clarification"},
    ),
    (
        CompleteTaskCommand(
            TASK_KEY,
            PROCESS_INSTANCE_KEY,
            "release",
            WorkflowAction.RELEASE,
        ),
        None,
    ),
)


@pytest.mark.parametrize(("command", "variables"), COMPLETIONS)
@pytest.mark.asyncio
async def test_completion_sends_only_allowlisted_variables(
    command: CompleteTaskCommand,
    variables: dict[str, str] | None,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    async with running_engine(handler) as engine:
        await engine.complete_task(command)

    expected: dict[str, Any] = {"action": command.action.value}
    if variables is not None:
        expected["variables"] = variables
    assert requests[0].method == "POST"
    assert requests[0].url.path == f"/v2/user-tasks/{TASK_KEY}/completion"
    assert request_json(requests[0]) == expected
