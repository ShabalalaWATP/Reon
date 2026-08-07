"""Direct persistence tests for draft locking, versioning and submission."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.models import User, UserRole
from istari_service.organisation_seed import seed_organisation_units
from istari_service.repositories.drafts import SqlAlchemyDraftRepository
from istari_service.schemas.drafts import (
    RequestDraftCreate,
    RequestDraftSubmit,
    RequestDraftUpdate,
)


@pytest.fixture
async def database() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await seed_organisation_units(session)
    yield engine, factory
    await engine.dispose()


def submission(expected_version: int) -> RequestDraftSubmit:
    return RequestDraftSubmit(
        expected_version=expected_version,
        title="Synthetic service request",
        service_category="Research",
        description="A sufficiently detailed synthetic request description.",
        desired_outcome="A useful fictional written response.",
        background_context="Synthetic context only.",
        required_by=datetime.now(UTC).date() + timedelta(days=7),
        required_by_reason="Needed for a fictional planning exercise.",
        preferred_deliverable_type="Plain text",
        success_criteria="The synthetic question is answered clearly.",
        requesting_business_area="Area A",
        intended_recipients=["Synthetic recipient"],
        sensitivity="STANDARD",
        handling_instructions="Retain synthetic content only.",
    )


@pytest.mark.asyncio
async def test_repository_covers_draft_lock_and_submission_branches(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        user = User(
            username="draft.owner@example.test",
            display_name="Draft Owner",
            password_hash="$argon2id$synthetic",
            role=UserRole.REQUESTER,
            scope="Area A",
        )
        session.add(user)
        await session.flush()
        actor = Actor(user.id, user.username, user.display_name, user.role, user.scope)
        repository = SqlAlchemyDraftRepository(session, process_id="service-request")

        first = await repository.create(
            actor,
            RequestDraftCreate(title="First", intended_recipients=[" Recipient "]),
        )
        second = await repository.create(actor, RequestDraftCreate(title="Second"))
        assert len(await repository.list_for_requester(user.id)) == 2
        assert await repository.get(first.id, user.id) is not None
        assert await repository.get(uuid4(), user.id) is None

        with pytest.raises(StaleVersion):
            await repository.update(
                first.id,
                actor,
                RequestDraftUpdate(expected_version=9, title="Stale"),
            )
        updated = await repository.update(
            first.id,
            actor,
            RequestDraftUpdate(
                expected_version=1,
                title="Updated",
                description="Still incomplete.",
            ),
        )
        assert updated.version == 2
        with pytest.raises(ObjectNotFound):
            await repository.update(
                uuid4(),
                actor,
                RequestDraftUpdate(expected_version=1, title="Missing"),
            )

        with pytest.raises(StaleVersion):
            await repository.delete(second.id, user.id, 2)
        await repository.delete(second.id, user.id, 1)

        with pytest.raises(StaleVersion):
            await repository.submit(first.id, actor, submission(1))
        command = submission(2)
        detail = await repository.submit(first.id, actor, command)
        repeated = await repository.submit(first.id, actor, command)
        assert repeated.id == detail.id
