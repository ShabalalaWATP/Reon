"""Independent worker composition, lifecycle and command-line boundaries."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

from istari_service.config import Environment, Settings
from istari_service.worker import async_main, build_iteration, main, parser
from istari_service.workflow.camunda import CamundaWorkflowEngine


def settings(*, notifications_enabled: bool = False) -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        notifications_enabled=notifications_enabled,
    )


@pytest.mark.parametrize(
    ("notifications_enabled", "expected_names"),
    [
        (
            False,
            {
                "workflow-start-dispatch",
                "workflow-cancellation-dispatch",
                "workflow-command-dispatch",
                "workflow-reconciliation",
                "membership-projection",
                "request-search-index",
            },
        ),
        (
            True,
            {
                "workflow-start-dispatch",
                "workflow-cancellation-dispatch",
                "workflow-command-dispatch",
                "workflow-reconciliation",
                "notification-projection",
                "membership-projection",
                "request-search-index",
            },
        ),
    ],
)
def test_iteration_composition_respects_notification_capability(
    notifications_enabled: bool,
    expected_names: set[str],
) -> None:
    iteration = build_iteration(
        settings(notifications_enabled=notifications_enabled),
        cast(CamundaWorkflowEngine, object()),
    )
    assert {job.name for job in iteration._jobs} == expected_names


class FakeClient:
    def __init__(self, *, fail_enter: bool = False) -> None:
        self.fail_enter = fail_enter
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> FakeClient:
        self.entered += 1
        if self.fail_enter:
            raise RuntimeError("synthetic client startup failure")
        return self

    async def __aexit__(self, *_values: object) -> None:
        self.exited += 1


@pytest.mark.parametrize("once", [True, False])
async def test_async_main_runs_once_or_continuously_and_always_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    once: bool,
) -> None:
    import istari_service.worker as worker

    client = FakeClient()
    iteration = AsyncMock()
    run_loop = AsyncMock()
    dispose = AsyncMock()
    monkeypatch.setattr(worker, "get_settings", lambda: settings())
    monkeypatch.setattr(worker, "camunda_client_configuration", lambda _value: object())
    monkeypatch.setattr(worker, "CamundaAsyncClient", lambda **_values: client)
    monkeypatch.setattr(worker, "CamundaWorkflowEngine", lambda _client: object())
    monkeypatch.setattr(worker, "build_iteration", lambda *_values: iteration)
    monkeypatch.setattr(worker, "run_worker", run_loop)
    monkeypatch.setattr(worker, "dispose_database", dispose)

    assert await async_main(argparse.Namespace(once=once)) == 0
    assert client.entered == client.exited == 1
    dispose.assert_awaited_once()
    if once:
        iteration.run_once.assert_awaited_once()
        run_loop.assert_not_awaited()
    else:
        iteration.run_once.assert_not_awaited()
        run_loop.assert_awaited_once()


async def test_async_main_cleans_database_when_client_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import istari_service.worker as worker

    client = FakeClient(fail_enter=True)
    dispose = AsyncMock()
    monkeypatch.setattr(worker, "get_settings", lambda: settings())
    monkeypatch.setattr(worker, "camunda_client_configuration", lambda _value: object())
    monkeypatch.setattr(worker, "CamundaAsyncClient", lambda **_values: client)
    monkeypatch.setattr(worker, "dispose_database", dispose)

    with pytest.raises(RuntimeError, match="startup failure"):
        await async_main(argparse.Namespace(once=True))
    assert client.entered == 1 and client.exited == 0
    dispose.assert_awaited_once()


def test_parser_and_main_return_process_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import istari_service.worker as worker

    assert parser().parse_args(["--once"]).once is True
    monkeypatch.setattr(worker, "async_main", lambda _arguments: object())
    monkeypatch.setattr(
        worker,
        "parser",
        lambda: SimpleNamespace(parse_args=lambda: argparse.Namespace(once=True)),
    )
    monkeypatch.setattr(worker.asyncio, "run", lambda _value: 7)
    assert main() == 7

    def interrupted(_value: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(worker.asyncio, "run", interrupted)
    assert main() == 130
