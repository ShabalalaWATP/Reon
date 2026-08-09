"""Atomic active-version selection under competing approved drafts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from configuration_support import (
    ConfigurationActors,
    draft_from_active,
    seed_configuration_context,
)
from istari_service.config import Environment, Settings
from istari_service.configuration_types import ConfigurationStatus
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.errors import StaleVersion
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.schemas.configuration import (
    ConfigurationDraftCreate,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
)
from istari_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)


@pytest.mark.asyncio
async def test_only_one_approved_draft_can_replace_the_same_active_version() -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        configuration_admin_enabled=True,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    sessions = create_session_factory(engine)
    try:
        async with sessions() as session, session.begin():
            actors = await seed_configuration_context(session)
            repository = SqlAlchemyConfigurationRepository(session)
            lifecycle = ConfigurationLifecycleService(
                repository,
                settings,
                clock=lambda: actors.now + timedelta(minutes=1),
            )
            first = await _approved_draft(
                lifecycle,
                actors,
                await draft_from_active(session, actors, label="First contender"),
            )
            second = await _approved_draft(
                lifecycle,
                actors,
                await draft_from_active(session, actors, label="Second contender"),
            )

            winner = await lifecycle.activate(
                actors.reviewer,
                first.id,
                _reason(
                    first.version, "Activate the first independently approved draft."
                ),
            )
            assert winner.status is ConfigurationStatus.ACTIVE
            with pytest.raises(StaleVersion):
                await lifecycle.activate(
                    actors.reviewer,
                    second.id,
                    _reason(
                        second.version,
                        "The stale second draft must not replace the winner.",
                    ),
                )
            stored_second = await repository.get_version(second.id)
            assert stored_second.status is ConfigurationStatus.AWAITING_APPROVAL
            active = await repository.active_bundle()
            assert active is not None and active.version.id == winner.id
    finally:
        await engine.dispose()


async def _approved_draft(
    lifecycle: ConfigurationLifecycleService,
    actors: ConfigurationActors,
    payload: ConfigurationDraftCreate,
) -> ConfigurationVersionDetail:
    draft = await lifecycle.create(actors.creator, payload)
    validated = await lifecycle.validate(
        actors.creator,
        draft.id,
        ConfigurationVersionCommand(expected_version=draft.version),
    )
    submitted = await lifecycle.submit(
        actors.creator,
        draft.id,
        _reason(validated.version, "Submit this contender for independent review."),
    )
    return await lifecycle.approve(
        actors.reviewer,
        draft.id,
        _reason(submitted.version, "Approve this exact contender without activation."),
    )


def _reason(version: int, reason: str) -> ConfigurationReasonCommand:
    return ConfigurationReasonCommand(expected_version=version, reason=reason)


@pytest.mark.asyncio
async def test_activation_state_is_flushed_before_evidence_is_inserted() -> None:
    events: list[str] = []
    session = SimpleNamespace(
        flush=AsyncMock(side_effect=lambda: events.append("flush")),
        add=Mock(side_effect=lambda _record: events.append("add activation")),
    )
    repository = SqlAlchemyConfigurationRepository(session)  # type: ignore[arg-type]
    active_id = uuid4()
    registry = SimpleNamespace(active_version_id=active_id, version=1)
    active = SimpleNamespace(
        status=ConfigurationStatus.ACTIVE,
        version=3,
    )
    candidate = SimpleNamespace(
        id=uuid4(),
        based_on_version_id=active_id,
        status=ConfigurationStatus.AWAITING_APPROVAL,
        activated_at=None,
        version=4,
    )
    approval = SimpleNamespace(id=uuid4(), snapshot_digest="a" * 64)
    repository.lock_registry = AsyncMock(return_value=registry)  # type: ignore[method-assign]
    repository.get_version = AsyncMock(return_value=active)  # type: ignore[method-assign]

    await repository.activate(
        candidate,
        approval,
        actor_id=uuid4(),
        reason="Activate the independently approved configuration.",
        now=datetime(2026, 8, 9, 17, 30, tzinfo=UTC),
    )

    assert events == ["flush", "flush", "add activation", "flush"]
