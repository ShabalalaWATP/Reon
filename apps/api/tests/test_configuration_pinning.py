"""Immutable request pinning and append-only lifecycle evidence tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from configuration_support import (
    activate_second_configuration,
    make_request,
    seed_configuration_context,
)
from mist_service.config import Environment, Settings
from mist_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationRegistry,
    RequestConfigurationPin,
)
from mist_service.configuration_readiness import configuration_runtime_is_ready
from mist_service.configuration_request_policy import (
    REQUEST_POLICY_SCHEMA,
    canonical_link_domains,
)
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.errors import InvalidAdministrationChange, ObjectNotFound
from mist_service.models import User, UserRole
from mist_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from mist_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from mist_service.repositories.configuration_policies import (
    load_request_configuration_policies,
)
from mist_service.schemas.configuration import ConfigurationReasonCommand


@pytest.fixture
async def pinning_database() -> AsyncIterator[
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
async def test_new_requests_pin_once_across_configuration_supersession(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, settings = pinning_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        await _set_active_workflow_availability(session, available=True)
        first_request = make_request(actors.requester_id)
        session.add(first_request)
        await session.flush()
        pins = SqlAlchemyConfigurationPinRepository(session)
        first_pin = await pins.pin_request(first_request.id, now=actors.now)
        repeated = await pins.pin_request(first_request.id, now=actors.now)
        assert repeated.id == first_pin.id
        stored_first = await session.scalar(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == first_request.id
            )
        )
        assert stored_first is not None
        assert stored_first.snapshot["processId"] == "service-request-v1"
        assert stored_first.snapshot["processVersion"] == 1
        assert stored_first.snapshot["requestPolicySchema"] == REQUEST_POLICY_SCHEMA
        organisation = stored_first.snapshot["organisation"]
        assert organisation["units"]
        assert organisation["edges"]
        assert organisation["candidateGroups"]
        catalogue = stored_first.snapshot["catalogue"]
        assert catalogue["serviceCategories"]
        assert catalogue["productTypes"]
        assert catalogue["artefactTypes"]
        domains = tuple(stored_first.snapshot["approvedLinkDomains"])
        assert canonical_link_domains(domains) == (
            domains,
            stored_first.snapshot["approvedLinkDomainsDigest"],
        )

        activated = await activate_second_configuration(session, settings, actors)

        assert (
            await pins.pin_request(
                first_request.id, now=actors.now + timedelta(minutes=1)
            )
        ).configuration_version_id == first_pin.configuration_version_id
        second_request = make_request(actors.requester_id)
        session.add(second_request)
        await session.flush()
        second_pin = await pins.pin_request(
            second_request.id, now=actors.now + timedelta(minutes=1)
        )
        assert second_pin.configuration_version_id == activated.id
        stored_second = await session.scalar(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == second_request.id
            )
        )
        assert stored_second is not None
        assert stored_second.snapshot["processId"] == "service-request-v2"
        assert stored_second.snapshot["processChecksum"] == "a" * 64

        approval = await session.scalar(
            select(ConfigurationApproval).where(
                ConfigurationApproval.configuration_version_id == activated.id
            )
        )
        activation = await session.scalar(
            select(ConfigurationActivation).where(
                ConfigurationActivation.configuration_version_id == activated.id
            )
        )
        assert approval is not None and activation is not None
        await _assert_append_only(session, stored_second, approval, activation)


@pytest.mark.asyncio
async def test_pinning_requires_an_effective_active_configuration(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        requester = User(
            username="pin.requester@example.test",
            email="pin.requester@example.test",
            display_name="Pin Requester",
            password_hash="$argon2id$synthetic",
            role=UserRole.REQUESTER,
            scope="Area A",
            is_active=True,
        )
        session.add_all([requester, ConfigurationRegistry(id=1)])
        await session.flush()
        request = make_request(requester.id)
        session.add(request)
        await session.flush()
        repository = SqlAlchemyConfigurationPinRepository(session)
        with pytest.raises(ObjectNotFound):
            await repository.pin_request(request.id, now=datetime.now(UTC))


@pytest.mark.asyncio
async def test_request_policies_are_loaded_in_one_statement(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    engine, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        await _set_active_workflow_availability(session, available=True)
        requests = [make_request(actors.requester_id) for _ in range(3)]
        session.add_all(requests)
        await session.flush()
        repository = SqlAlchemyConfigurationPinRepository(session)
        for request in requests:
            await repository.pin_request(request.id, now=actors.now)

        statements: list[str] = []

        def capture_statement(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if "request_configuration_pins" in statement:
                statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
        try:
            policies = await load_request_configuration_policies(
                session, {request.id for request in requests} | {uuid4()}
            )
        finally:
            event.remove(
                engine.sync_engine,
                "before_cursor_execute",
                capture_statement,
            )

        assert set(policies) == {request.id for request in requests}
        assert len(statements) == 1


@pytest.mark.asyncio
async def test_pin_rechecks_after_a_prior_transaction_and_requires_request_row(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        await _set_active_workflow_availability(session, available=True)
        request = make_request(actors.requester_id)
        session.add(request)
        await session.flush()
        request_id = request.id
        effective_at = actors.now

    async with sessions() as session, session.begin():
        first = await SqlAlchemyConfigurationPinRepository(session).pin_request(
            request_id,
            now=effective_at,
        )
        pin_id = first.id

    async with sessions() as session, session.begin():
        repository = SqlAlchemyConfigurationPinRepository(session)
        repeated = await repository.pin_request(request_id, now=effective_at)
        count = await session.scalar(select(func.count(RequestConfigurationPin.id)))
        assert repeated.id == pin_id
        assert count == 1
        with pytest.raises(ObjectNotFound):
            await repository.pin_request(uuid4(), now=effective_at)


@pytest.mark.asyncio
async def test_pin_rejects_an_unavailable_active_workflow(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        request = make_request(actors.requester_id)
        session.add(request)
        await session.flush()
        repository = SqlAlchemyConfigurationPinRepository(session)
        with pytest.raises(
            RuntimeError,
            match="active workflow definition is unavailable",
        ):
            await repository.pin_request(request.id, now=actors.now)
        assert await session.scalar(select(RequestConfigurationPin.id)) is None


@pytest.mark.asyncio
async def test_runtime_and_new_pins_reject_mismatched_snapshot_evidence(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        await _set_active_workflow_availability(session, available=True)
        approval = await session.scalar(select(ConfigurationApproval))
        assert approval is not None
        await session.execute(
            update(ConfigurationApproval)
            .where(ConfigurationApproval.id == approval.id)
            .values(snapshot_digest="0" * 64)
        )
        request = make_request(actors.requester_id)
        session.add(request)
        await session.flush()

        assert not await configuration_runtime_is_ready(session, now=actors.now)
        with pytest.raises(RuntimeError, match="approval evidence is invalid"):
            await SqlAlchemyConfigurationPinRepository(session).pin_request(
                request.id,
                now=actors.now,
            )


@pytest.mark.asyncio
async def test_component_replacement_rejects_non_draft_versions_before_deletion(
    pinning_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession], Settings],
) -> None:
    _, sessions, _ = pinning_database
    async with sessions() as session, session.begin():
        await seed_configuration_context(session)
        repository = SqlAlchemyConfigurationRepository(session)
        active = await repository.active_bundle()
        assert active is not None
        specification = active.specification()
        with pytest.raises(InvalidAdministrationChange, match="Only Draft"):
            await repository.replace_components(active.version.id, specification)
        unchanged = await repository.active_bundle()
        assert unchanged is not None
        assert unchanged.specification() == specification


async def _set_active_workflow_availability(
    session: AsyncSession,
    *,
    available: bool,
) -> None:
    repository = SqlAlchemyConfigurationRepository(session)
    active = await repository.active_bundle()
    assert active is not None
    workflow = await repository.approved_workflow(
        active.workflow_template.workflow_definition_id
    )
    assert workflow is not None
    workflow.is_available = available
    await session.flush()


async def _assert_append_only(
    session: AsyncSession,
    pin: RequestConfigurationPin,
    approval: ConfigurationApproval,
    activation: ConfigurationActivation,
) -> None:
    for record, field, replacement in (
        (pin, "snapshot", {"changed": True}),
        (approval, "reason", "Changed approval evidence"),
        (activation, "reason", "Changed activation evidence"),
    ):
        with pytest.raises(ValueError, match="append-only"):
            async with session.begin_nested():
                setattr(record, field, replacement)
                await session.flush()


def _reason(version: int, reason: str) -> ConfigurationReasonCommand:
    return ConfigurationReasonCommand(expected_version=version, reason=reason)
