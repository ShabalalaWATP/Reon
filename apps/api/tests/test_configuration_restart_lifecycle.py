"""Application restart preserves the approved configuration projection."""

from typing import Any, cast

import pytest

import mist_service.main as main_module
from mist_service.main import create_app
from mist_service.workflow.fake import FakeWorkflowEngine
from test_coverage_lifecycle import (
    FastHasher,
    SessionFactoryDouble,
    make_settings,
)


@pytest.mark.asyncio
async def test_lifespan_restores_active_configuration_without_fixture_reseed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    restored: list[object] = []
    initialised: list[object] = []

    async def restore(session: object) -> bool:
        restored.append(session)
        return True

    async def forbidden(_session: object) -> int:
        raise AssertionError("active configuration must not be overwritten")

    async def initialise(session: object) -> None:
        initialised.append(session)

    monkeypatch.setattr(
        main_module,
        "restore_active_configuration_projection",
        restore,
    )
    monkeypatch.setattr(main_module, "seed_organisation_units", forbidden)
    monkeypatch.setattr(main_module, "seed_baseline_configuration", forbidden)
    monkeypatch.setattr(main_module, "initialise_platform_classification", initialise)
    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
    )
    async with application.router.lifespan_context(application):
        pass
    assert len(restored) == 1
    assert len(initialised) == 1


@pytest.mark.asyncio
async def test_lifespan_refreshes_projection_after_demo_user_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    restored: list[object] = []

    async def restore(session: object) -> bool:
        restored.append(session)
        return True

    async def no_seed(*_args: object, **_kwargs: object) -> int:
        return 0

    monkeypatch.setattr(
        main_module,
        "restore_active_configuration_projection",
        restore,
    )
    monkeypatch.setattr(main_module, "seed_demo_users", no_seed)
    monkeypatch.setattr(main_module, "initialise_admin_identity_sequence", no_seed)
    monkeypatch.setattr(main_module, "initialise_admin_audit_anchor", no_seed)
    monkeypatch.setattr(main_module, "initialise_platform_classification", no_seed)
    application = create_app(
        settings=make_settings(allow_demo_users=True),
        session_factory=cast(Any, SessionFactoryDouble()),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
    )
    async with application.router.lifespan_context(application):
        pass
    assert len(restored) == 2
