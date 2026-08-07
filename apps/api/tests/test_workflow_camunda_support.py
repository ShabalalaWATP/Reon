"""Shared synthetic HTTP fixtures for Camunda adapter tests."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
from camunda_orchestration_sdk import CamundaAsyncClient

from istari_service.workflow.camunda import CamundaWorkflowEngine

REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")
REQUESTER_ID = UUID("00000000-0000-4000-8000-000000000002")
SPECIALIST_ID = UUID("00000000-0000-4000-8000-000000000003")
ASSIGNEE_ID = UUID("00000000-0000-4000-8000-000000000004")
PROCESS_DEFINITION_KEY = "2251799813685249"
PROCESS_INSTANCE_KEY = "2251799813685250"
TASK_KEY = "2251799813685251"
ELEMENT_INSTANCE_KEY = "2251799813685252"
ROOT_PROCESS_INSTANCE_KEY = PROCESS_INSTANCE_KEY
TENANT_ID = "tenant-a"

Handler = Callable[
    [httpx.Request],
    httpx.Response | Awaitable[httpx.Response],
]


def creation_result(**updates: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "processDefinitionId": "service_request",
        "processDefinitionVersion": 1,
        "tenantId": "<default>",
        "variables": {
            "requestId": str(REQUEST_ID),
            "requesterId": str(REQUESTER_ID),
        },
        "processDefinitionKey": PROCESS_DEFINITION_KEY,
        "processInstanceKey": PROCESS_INSTANCE_KEY,
        "tags": [],
        "businessId": str(REQUEST_ID),
    }
    result.update(updates)
    return result


def process_result(**updates: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "processDefinitionId": "service_request",
        "processDefinitionName": "Synthetic service request",
        "processDefinitionVersion": 1,
        "processDefinitionVersionTag": None,
        "startDate": "2026-08-06T09:00:00.000Z",
        "endDate": None,
        "state": "ACTIVE",
        "hasIncident": False,
        "tenantId": "<default>",
        "processInstanceKey": PROCESS_INSTANCE_KEY,
        "processDefinitionKey": PROCESS_DEFINITION_KEY,
        "parentProcessInstanceKey": None,
        "parentElementInstanceKey": None,
        "rootProcessInstanceKey": ROOT_PROCESS_INSTANCE_KEY,
        "tags": [],
        "businessId": str(REQUEST_ID),
    }
    result.update(updates)
    return result


def task_result(**updates: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tenantId": "<default>",
        "userTaskKey": TASK_KEY,
        "name": "Intake review",
        "processInstanceKey": PROCESS_INSTANCE_KEY,
        "rootProcessInstanceKey": ROOT_PROCESS_INSTANCE_KEY,
        "processDefinitionKey": PROCESS_DEFINITION_KEY,
        "elementInstanceKey": ELEMENT_INSTANCE_KEY,
        "processDefinitionId": "service_request",
        "processName": "Synthetic service request",
        "state": "CREATED",
        "candidateGroups": [],
        "candidateUsers": [],
        "elementId": "intake_review",
        "creationDate": "2026-08-06T09:00:00.000Z",
        "customHeaders": {},
        "priority": 50,
        "tags": [],
        "assignee": None,
        "completionDate": None,
        "dueDate": None,
        "externalFormReference": None,
        "followUpDate": None,
        "processDefinitionVersion": 1,
        "formKey": None,
    }
    result.update(updates)
    return result


def page(*items: dict[str, Any]) -> dict[str, Any]:
    return {
        "items": list(items),
        "page": {
            "totalItems": len(items),
            "hasMoreTotalItems": False,
            "startCursor": "c3RhcnQ=" if items else None,
            "endCursor": "ZW5k" if items else None,
        },
    }


def problem(status: int, title: str = "Rejected") -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": "Synthetic Camunda response",
        "instance": "/v2/synthetic",
    }


def request_json(request: httpx.Request) -> dict[str, Any]:
    return {} if not request.content else json.loads(request.content)


@asynccontextmanager
async def running_engine(
    handler: Handler,
    *,
    recovery_attempts: int = 5,
    recovery_delay: float = 0.05,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> AsyncIterator[CamundaWorkflowEngine]:
    client = CamundaAsyncClient(
        configuration={
            "CAMUNDA_REST_ADDRESS": "https://camunda.test",
            "CAMUNDA_AUTH_STRATEGY": "NONE",
        },
        httpx_args={"transport": httpx.MockTransport(handler)},
    )
    options: dict[str, Any] = {
        "start_recovery_attempts": recovery_attempts,
        "start_recovery_delay_seconds": recovery_delay,
    }
    if sleep is not None:
        options["sleep"] = sleep
    try:
        yield CamundaWorkflowEngine(client, **options)
    finally:
        await client.aclose()
