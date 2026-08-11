"""Single Camunda SDK lifecycle boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from istari_service.config import Environment, Settings
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow_runtime import (
    CamundaClientFactory,
    WorkflowAdapterFactory,
    managed_camunda_engine,
)

ENTRY_POINTS = ("main.py", "worker.py")


def settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        camunda_rest_address="http://workflow.local",
    )


class ClientDouble:
    def __init__(self, *, fail_enter: bool = False) -> None:
        self.fail_enter = fail_enter
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> ClientDouble:
        self.entered += 1
        if self.fail_enter:
            raise RuntimeError("synthetic entry failure")
        return self

    async def __aexit__(self, *_values: object) -> None:
        self.exited += 1


@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_process_entry_points_do_not_import_the_camunda_sdk(entry_point: str) -> None:
    source = Path("src/istari_service", entry_point).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not any(
        module.startswith("camunda_orchestration_sdk") for module in imported_modules
    )


async def test_runtime_owns_configuration_adapter_and_client_exit() -> None:
    client = ClientDouble()
    configurations: list[dict[str, str]] = []
    engine = cast(WorkflowEngine, object())

    def client_factory(*, configuration: dict[str, str]) -> ClientDouble:
        configurations.append(configuration)
        return client

    async with managed_camunda_engine(
        settings(),
        client_factory=cast(CamundaClientFactory, client_factory),
        adapter_factory=cast(WorkflowAdapterFactory, lambda _value: engine),
    ) as actual:
        assert actual is engine
        assert client.entered == 1 and client.exited == 0

    assert configurations == [
        {
            "CAMUNDA_REST_ADDRESS": "http://workflow.local/v2",
            "CAMUNDA_AUTH_STRATEGY": "NONE",
            "CAMUNDA_SDK_LOG_LEVEL": "warn",
        }
    ]
    assert client.exited == 1


@pytest.mark.parametrize("failure", ["entry", "adapter"])
async def test_runtime_fails_closed_and_closes_only_an_entered_client(
    failure: str,
) -> None:
    client = ClientDouble(fail_enter=failure == "entry")

    def client_factory(**_values: Any) -> ClientDouble:
        return client

    def adapter_factory(_client: object) -> WorkflowEngine:
        raise RuntimeError("synthetic adapter failure")

    with pytest.raises(RuntimeError, match=f"synthetic {failure} failure"):
        async with managed_camunda_engine(
            settings(),
            client_factory=cast(CamundaClientFactory, client_factory),
            adapter_factory=cast(WorkflowAdapterFactory, adapter_factory),
        ):
            pytest.fail("a failed runtime must not yield an engine")

    assert client.entered == 1
    assert client.exited == (0 if failure == "entry" else 1)
