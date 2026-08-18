"""Configuration lifecycle, separation-of-duty and query behaviour."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from configuration_support import (
    CollectingConfigurationPublisher,
    draft_from_active,
    seed_configuration_context,
)
from mist_service.config import Environment, Settings
from mist_service.configuration_digest import configuration_digest
from mist_service.configuration_events import ConfigurationEventType
from mist_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationUnitRevision,
    ConfigurationValidationFinding,
)
from mist_service.configuration_types import ConfigurationStatus, FindingSeverity
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.domain import Actor
from mist_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
    InvalidAdministrationChange,
    StaleVersion,
)
from mist_service.models import UserRole
from mist_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from mist_service.schemas.configuration import (
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
)
from mist_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)
from mist_service.services.configuration_query_service import (
    ConfigurationQueryService,
)


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
async def test_configuration_approval_activation_and_queries(
    configuration_database: tuple[
        AsyncEngine, async_sessionmaker[AsyncSession], Settings
    ],
) -> None:
    _, sessions, settings = configuration_database
    publisher = CollectingConfigurationPublisher()
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        repository = SqlAlchemyConfigurationRepository(session)
        lifecycle = ConfigurationLifecycleService(
            repository,
            repository,
            repository,
            repository,
            settings,
            publisher,
            clock=lambda: actors.now + timedelta(minutes=1),
        )
        query = ConfigurationQueryService(repository, settings)
        payload = await draft_from_active(session, actors)

        created = await lifecycle.create(actors.creator, payload)
        assert created.status is ConfigurationStatus.DRAFT
        assert created.version == 1
        with pytest.raises(InvalidAdministrationChange, match="awaiting approval"):
            await lifecycle.approve(
                actors.reviewer,
                created.id,
                _reason(created.version, "A draft cannot be approved."),
            )
        with pytest.raises(StaleVersion):
            await lifecycle.validate(
                actors.creator,
                created.id,
                ConfigurationVersionCommand(expected_version=99),
            )

        validated = await lifecycle.validate(
            actors.creator,
            created.id,
            ConfigurationVersionCommand(expected_version=created.version),
        )
        assert validated.status is ConfigurationStatus.VALIDATED
        assert {item.severity for item in validated.findings} == {
            FindingSeverity.WARNING
        }
        assert any(item.code == "TEAM_AWAITING_STAFFING" for item in validated.findings)

        submitted = await lifecycle.submit(
            actors.creator,
            created.id,
            _reason(
                validated.version, "Submit the exact validated synthetic snapshot."
            ),
        )
        assert submitted.status is ConfigurationStatus.AWAITING_APPROVAL
        with pytest.raises(InvalidAdministrationChange, match="different"):
            await lifecycle.approve(
                actors.creator,
                created.id,
                _reason(
                    submitted.version, "Creator cannot self-approve this snapshot."
                ),
            )

        approved = await lifecycle.approve(
            actors.reviewer,
            created.id,
            _reason(
                submitted.version, "Independent review confirms the exact snapshot."
            ),
        )
        assert approved.approval is not None
        assert approved.approval.reviewed_version == submitted.version
        assert len(approved.approval.snapshot_digest) == 64
        migration = _sealing_migration()
        migrated_digest = await session.run_sync(
            lambda sync_session: migration._stored_snapshot_digest(
                sync_session.connection(),
                created.id
                if sync_session.bind.dialect.name != "sqlite"
                else created.id.hex,
            )
        )
        assert migrated_digest == configuration_digest(
            (await repository.bundle(created.id)).specification()
        )
        with pytest.raises(InvalidAdministrationChange, match="already has a decision"):
            await lifecycle.approve(
                actors.reviewer,
                created.id,
                _reason(approved.version, "A decision cannot be duplicated."),
            )
        with pytest.raises(InvalidAdministrationChange, match="creator"):
            await lifecycle.activate(
                actors.creator,
                created.id,
                _reason(
                    approved.version, "Creator cannot activate their own snapshot."
                ),
            )

        unit = await session.scalar(
            select(ConfigurationUnitRevision).where(
                ConfigurationUnitRevision.configuration_version_id == created.id
            )
        )
        assert unit is not None
        original_name = unit.name
        unit.name = "Tampered outside the configuration service"
        await session.flush()
        with pytest.raises(InvalidAdministrationChange, match="no longer matches"):
            await lifecycle.activate(
                actors.reviewer,
                created.id,
                _reason(approved.version, "Reject changed approval evidence."),
            )
        unit.name = original_name
        await session.flush()

        activated = await lifecycle.activate(
            actors.reviewer,
            created.id,
            _reason(
                approved.version, "Activate for new requests after independent review."
            ),
        )
        assert activated.status is ConfigurationStatus.ACTIVE
        versions = await query.list_versions(actors.reviewer)
        assert [item.sequence for item in versions.items] == [2, 1]
        assert versions.items[1].status is ConfigurationStatus.SUPERSEDED
        assert (await query.active(actors.reviewer)).id == activated.id
        assert (await query.get_version(actors.reviewer, activated.id)).approval

        definitions = await query.workflow_definitions(actors.reviewer)
        assert [item.process_id for item in definitions.items] == ["service-request-v2"]
        preview = await query.preview(actors.reviewer, activated.id)
        assert "WORKFLOW_AFFECTED" in {item.type.value for item in preview.changes}
        snapshot = await query.organisation(
            actors.reviewer, activated.id, at=actors.now
        )
        assert len(snapshot.units) == len(activated.units)
        assert sum(item.parent_unit_id is None for item in snapshot.units) == 1

        assert [event.type for event in publisher.events] == [
            ConfigurationEventType.AWAITING_REVIEW,
            ConfigurationEventType.ACTIVATED,
            ConfigurationEventType.SUPERSEDED,
        ]
        activation = await session.scalar(
            select(ConfigurationActivation).where(
                ConfigurationActivation.configuration_version_id == created.id
            )
        )
        assert activation is not None and activation.superseded_version_id is not None
        assert activation.snapshot_digest == approved.approval.snapshot_digest


@pytest.mark.asyncio
async def test_rejection_invalid_validation_and_access_boundaries(
    configuration_database: tuple[
        AsyncEngine, async_sessionmaker[AsyncSession], Settings
    ],
) -> None:
    _, sessions, settings = configuration_database
    publisher = CollectingConfigurationPublisher()
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        repository = SqlAlchemyConfigurationRepository(session)
        lifecycle = ConfigurationLifecycleService(
            repository,
            repository,
            repository,
            repository,
            settings,
            publisher,
            clock=lambda: actors.now,
        )
        payload = await draft_from_active(
            session, actors, label="Invalid then rejected"
        )
        payload.units[0].name = "Changed after schema construction"
        payload.workflow_template.core_fields.pop()
        created = await lifecycle.create(actors.creator, payload)
        invalid = await lifecycle.validate(
            actors.creator,
            created.id,
            ConfigurationVersionCommand(expected_version=created.version),
        )
        assert invalid.status is ConfigurationStatus.DRAFT
        assert invalid.validated_at is None
        assert any(item.code == "CORE_FIELDS_INVALID" for item in invalid.findings)
        with pytest.raises(InvalidAdministrationChange, match="Validated"):
            await lifecycle.submit(
                actors.creator,
                created.id,
                _reason(invalid.version, "An invalid draft cannot be submitted."),
            )

        valid_payload = await draft_from_active(session, actors, label="Rejected draft")
        draft = await lifecycle.create(actors.creator, valid_payload)
        validated = await lifecycle.validate(
            actors.creator,
            draft.id,
            ConfigurationVersionCommand(expected_version=draft.version),
        )
        submitted = await lifecycle.submit(
            actors.creator,
            draft.id,
            _reason(validated.version, "Submit this separate synthetic snapshot."),
        )
        rejected = await lifecycle.reject(
            actors.reviewer,
            draft.id,
            _reason(
                submitted.version, "Reject because the rollout evidence is incomplete."
            ),
        )
        assert rejected.status is ConfigurationStatus.REJECTED
        assert rejected.approval is not None
        assert publisher.events[-1].type is ConfigurationEventType.REJECTED
        with pytest.raises(InvalidAdministrationChange, match="approved"):
            await lifecycle.activate(
                actors.reviewer,
                draft.id,
                _reason(rejected.version, "A rejected version cannot be activated."),
            )

        non_admin = Actor(
            id=actors.requester_id,
            username="requester",
            display_name="Requester",
            role=UserRole.REQUESTER,
            scope="Area A",
        )
        with pytest.raises(AdministrationAccessDenied):
            await ConfigurationQueryService(repository, settings).list_versions(
                non_admin
            )
        disabled = settings.model_copy(update={"configuration_admin_enabled": False})
        with pytest.raises(AdministrationUnavailable):
            await ConfigurationQueryService(repository, disabled).list_versions(
                actors.creator
            )
        assert await session.scalar(select(ConfigurationValidationFinding.id))
        assert await session.scalar(select(ConfigurationApproval.id))


def _reason(version: int, reason: str) -> ConfigurationReasonCommand:
    return ConfigurationReasonCommand(expected_version=version, reason=reason)


def test_sealing_migration_only_decodes_declared_json_columns() -> None:
    migration = _sealing_migration()

    assert migration._normalise_field("name", "[1]") == "[1]"
    assert migration._normalise_field("label", '{"team":"SSG"}') == ('{"team":"SSG"}')
    assert migration._normalise_field("service_categories", '["Research"]') == [
        "Research"
    ]


def _sealing_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0018_configuration_snapshot_sealing.py"
    )
    specification = spec_from_file_location("configuration_sealing_migration", path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module
