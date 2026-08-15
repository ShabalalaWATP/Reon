"""Defence-in-depth checks for configuration approval evidence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from configuration_support import seed_configuration_context
from mist_service.config import Environment, Settings
from mist_service.configuration_integrity import snapshot_evidence_is_valid
from mist_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationVersion,
)
from mist_service.configuration_types import ApprovalDecision
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.models import User
from mist_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)


@pytest.fixture
async def integrity_database() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        configuration_admin_enabled=True,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    yield engine, create_session_factory(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_integrity_rejects_missing_activation_and_rejected_approval(
    integrity_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = integrity_database
    async with sessions() as session, session.begin():
        await seed_configuration_context(session)
        active = await SqlAlchemyConfigurationRepository(session).active_bundle()
        assert active is not None
        specification = active.specification()
        assert not await snapshot_evidence_is_valid(session, uuid4(), specification)

        await session.execute(
            update(ConfigurationApproval)
            .where(ConfigurationApproval.configuration_version_id == active.version.id)
            .values(decision=ApprovalDecision.REJECTED)
        )
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )


@pytest.mark.asyncio
async def test_integrity_rejects_structurally_forged_evidence(
    integrity_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = integrity_database
    async with sessions() as session, session.begin():
        actors = await seed_configuration_context(session)
        active = await SqlAlchemyConfigurationRepository(session).active_bundle()
        assert active is not None and active.approval is not None
        specification = active.specification()
        approval = active.approval
        activation = await session.scalar(
            select(ConfigurationActivation).where(
                ConfigurationActivation.configuration_version_id == active.version.id
            )
        )
        assert activation is not None
        assert await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )

        reviewed_version = approval.reviewed_version
        await session.execute(
            update(ConfigurationApproval)
            .where(ConfigurationApproval.id == approval.id)
            .values(reviewed_version=reviewed_version + 1)
        )
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )
        await session.execute(
            update(ConfigurationApproval)
            .where(ConfigurationApproval.id == approval.id)
            .values(reviewed_version=reviewed_version)
        )

        approver = await session.get(User, approval.actor_user_id)
        assert approver is not None
        await session.execute(
            update(User).where(User.id == approver.id).values(is_active=False)
        )
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )
        await session.execute(
            update(User).where(User.id == approver.id).values(is_active=True)
        )
        await session.refresh(approver)

        await session.execute(
            update(ConfigurationActivation)
            .where(ConfigurationActivation.id == activation.id)
            .values(activated_by_user_id=active.version.created_by_user_id)
        )
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )
        await session.execute(
            update(ConfigurationActivation)
            .where(ConfigurationActivation.id == activation.id)
            .values(activated_by_user_id=approval.actor_user_id)
        )

        await session.execute(
            update(ConfigurationActivation)
            .where(ConfigurationActivation.id == activation.id)
            .values(activated_by_user_id=actors.requester_id)
        )
        await session.refresh(activation)
        requester = await session.get(User, actors.requester_id)
        assert approver.is_active
        assert requester is not None and requester.is_active
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )
        await session.execute(
            update(ConfigurationActivation)
            .where(ConfigurationActivation.id == activation.id)
            .values(activated_by_user_id=approval.actor_user_id)
        )

        await session.execute(
            update(ConfigurationVersion)
            .where(ConfigurationVersion.id == active.version.id)
            .values(status="SUPERSEDED")
        )
        assert not await snapshot_evidence_is_valid(
            session, active.version.id, specification
        )
