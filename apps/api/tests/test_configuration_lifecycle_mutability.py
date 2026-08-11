"""Mutability boundaries for proposed configuration snapshots."""

from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from configuration_support import draft_from_active, seed_configuration_context
from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.errors import InvalidAdministrationChange
from istari_service.repositories.configuration import SqlAlchemyConfigurationRepository
from istari_service.schemas.configuration import (
    ConfigurationDraftReplace,
    ConfigurationVersionCommand,
)
from istari_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)
from istari_service.text_safety import normalise_display_name
from test_configuration_lifecycle import _reason


@pytest.fixture
async def configuration_database() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings]
]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        configuration_admin_enabled=True,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    yield engine, create_session_factory(engine), settings
    await engine.dispose()


@pytest.mark.asyncio
async def test_proposals_are_mutable_only_before_validation_and_activation_time(
    configuration_database: tuple[
        AsyncEngine, async_sessionmaker[AsyncSession], Settings
    ],
) -> None:
    _, sessions, settings = configuration_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        lifecycle = ConfigurationLifecycleService(
            SqlAlchemyConfigurationRepository(session),
            settings,
            clock=lambda: actors.now - timedelta(seconds=1),
        )
        payload = await draft_from_active(session, actors, label="Editable proposal")
        proposal = await lifecycle.create(actors.creator, payload)

        replacement = ConfigurationDraftReplace(
            **payload.model_dump(),
            expected_version=proposal.version,
        )
        replacement.label = "Replaced editable proposal"
        replaced = await lifecycle.replace(actors.creator, proposal.id, replacement)
        assert replaced.label == "Replaced editable proposal"
        assert replaced.version == proposal.version + 1

        self_based = replacement.model_copy(
            update={
                "based_on_version_id": proposal.id,
                "expected_version": replaced.version,
            }
        )
        with pytest.raises(InvalidAdministrationChange, match="itself"):
            await lifecycle.replace(actors.creator, proposal.id, self_based)

        other_payload = await draft_from_active(session, actors, label="Other proposal")
        other_payload.based_on_version_id = proposal.id
        with pytest.raises(InvalidAdministrationChange, match="immutable"):
            await lifecycle.create(actors.creator, other_payload)

        validated = await lifecycle.validate(
            actors.creator,
            proposal.id,
            ConfigurationVersionCommand(expected_version=replaced.version),
        )
        with pytest.raises(InvalidAdministrationChange, match="Draft"):
            await lifecycle.replace(
                actors.creator,
                proposal.id,
                replacement.model_copy(update={"expected_version": validated.version}),
            )
        submitted = await lifecycle.submit(
            actors.creator,
            proposal.id,
            _reason(
                validated.version, "Submit after the exact proposal has validated."
            ),
        )
        approved = await lifecycle.approve(
            actors.reviewer,
            proposal.id,
            _reason(
                submitted.version, "Independently approve this future configuration."
            ),
        )
        with pytest.raises(InvalidAdministrationChange, match="effective time"):
            await lifecycle.activate(
                actors.reviewer,
                proposal.id,
                _reason(
                    approved.version, "Activation must wait for its effective time."
                ),
            )


def test_display_names_reject_bidirectional_control_characters() -> None:
    with pytest.raises(ValueError, match="2 to 120 visible"):
        normalise_display_name("x")
    with pytest.raises(ValueError, match="control or bidirectional"):
        normalise_display_name("SSG\N{RIGHT-TO-LEFT OVERRIDE}Team")
