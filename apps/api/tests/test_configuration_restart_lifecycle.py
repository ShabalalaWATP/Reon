"""Application restart preserves the approved configuration projection."""

from typing import Any, cast

import pytest

import istari_service.main as main_module
from istari_service.main import create_app
from istari_service.workflow.fake import FakeWorkflowEngine
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

    async def restore(session: object) -> bool:
        restored.append(session)
        return True

    async def forbidden(_session: object) -> int:
        raise AssertionError("active configuration must not be overwritten")

    monkeypatch.setattr(
        main_module,
        "restore_active_configuration_projection",
        restore,
    )
    monkeypatch.setattr(main_module, "seed_organisation_units", forbidden)
    monkeypatch.setattr(main_module, "seed_baseline_configuration", forbidden)
    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
        start_background_worker=False,
    )
    async with application.router.lifespan_context(application):
        pass
    assert len(restored) == 2
