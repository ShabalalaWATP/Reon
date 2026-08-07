"""Configuration lifecycle, separation-of-duty and query behaviour."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from configuration_support import (
    CollectingConfigurationPublisher,
    draft_from_active,
    seed_configuration_context,
)
from istari_service.config import Environment, Settings
from istari_service.configuration_events import ConfigurationEventType
from istari_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationValidationFinding,
)
from istari_service.configuration_types import ConfigurationStatus, FindingSeverity
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.domain import Actor
from istari_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
    InvalidAdministrationChange,
    StaleVersion,
)
from istari_service.models import UserRole
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.schemas.configuration import (
    ConfigurationDraftReplace,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
)
from istari_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)
from istari_service.services.configuration_query_service import (
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
        activation = await session.scalar(select(ConfigurationActivation))
        assert activation is not None and activation.superseded_version_id is not None


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
            repository, settings, publisher, clock=lambda: actors.now
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


@pytest.mark.asyncio
async def test_drafts_are_mutable_only_before_validation_and_activation_time(
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
        payload = await draft_from_active(session, actors, label="Editable draft")
        draft = await lifecycle.create(actors.creator, payload)

        replacement = ConfigurationDraftReplace(
            **payload.model_dump(),
            expected_version=draft.version,
        )
        replacement.label = "Replaced editable draft"
        replaced = await lifecycle.replace(actors.creator, draft.id, replacement)
        assert replaced.label == "Replaced editable draft"
        assert replaced.version == draft.version + 1

        self_based = replacement.model_copy(
            update={
                "based_on_version_id": draft.id,
                "expected_version": replaced.version,
            }
        )
        with pytest.raises(InvalidAdministrationChange, match="itself"):
            await lifecycle.replace(actors.creator, draft.id, self_based)

        other_payload = await draft_from_active(session, actors, label="Other draft")
        other_payload.based_on_version_id = draft.id
        with pytest.raises(InvalidAdministrationChange, match="immutable"):
            await lifecycle.create(actors.creator, other_payload)

        validated = await lifecycle.validate(
            actors.creator,
            draft.id,
            ConfigurationVersionCommand(expected_version=replaced.version),
        )
        with pytest.raises(InvalidAdministrationChange, match="Draft"):
            await lifecycle.replace(
                actors.creator,
                draft.id,
                replacement.model_copy(update={"expected_version": validated.version}),
            )
        submitted = await lifecycle.submit(
            actors.creator,
            draft.id,
            _reason(validated.version, "Submit after the exact draft has validated."),
        )
        approved = await lifecycle.approve(
            actors.reviewer,
            draft.id,
            _reason(
                submitted.version, "Independently approve this future configuration."
            ),
        )
        with pytest.raises(InvalidAdministrationChange, match="effective time"):
            await lifecycle.activate(
                actors.reviewer,
                draft.id,
                _reason(
                    approved.version, "Activation must wait for its effective time."
                ),
            )


def _reason(version: int, reason: str) -> ConfigurationReasonCommand:
    return ConfigurationReasonCommand(expected_version=version, reason=reason)
