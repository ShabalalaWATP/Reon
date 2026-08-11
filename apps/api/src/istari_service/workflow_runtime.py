"""Managed construction of the SDK-backed workflow engine adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, cast

from camunda_orchestration_sdk import CamundaAsyncClient

from istari_service.config import Settings
from istari_service.workflow.camunda import CamundaWorkflowEngine
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow_client import camunda_client_configuration

CamundaClientFactory = Callable[..., CamundaAsyncClient]
WorkflowAdapterFactory = Callable[[CamundaAsyncClient], WorkflowEngine]
WorkflowRuntimeFactory = Callable[
    [Settings], AbstractAsyncContextManager[WorkflowEngine]
]


@asynccontextmanager
async def managed_camunda_engine(
    settings: Settings,
    *,
    client_factory: CamundaClientFactory = CamundaAsyncClient,
    adapter_factory: WorkflowAdapterFactory = CamundaWorkflowEngine,
) -> AsyncIterator[WorkflowEngine]:
    """Fail closed while owning one Camunda client and adapter lifecycle."""

    client = client_factory(
        configuration=cast(Any, camunda_client_configuration(settings))
    )
    async with client as entered_client:
        yield adapter_factory(entered_client)
