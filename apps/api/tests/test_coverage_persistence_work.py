"""Remaining SQLAlchemy work-repository branches."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.organisation_models import UserOrganisationMembership
from istari_service.organisation_seed import organisation_id, seed_organisation_units
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.schemas.work import ProgressRequest
from test_work_repository import (
    actor_from,
    make_user,
    seed_work,
)


@pytest.fixture
async def work_database() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    yield engine, create_session_factory(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_specialist_listing_is_active_team_scoped_and_ordered(
    work_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = work_database
    async with factory() as session:
        await seed_organisation_units(session)
        second = make_user(UserRole.DELIVERY_SPECIALIST, "OSG Team")
        second.display_name = "Synthetic Bravo"
        first = make_user(UserRole.DELIVERY_SPECIALIST, "OSG Team")
        first.display_name = "Synthetic Alpha"
        inactive = make_user(UserRole.DELIVERY_SPECIALIST, "OSG Team")
        inactive.is_active = False
        another_team = make_user(UserRole.DELIVERY_SPECIALIST, "Cedar Team")
        wrong_role = make_user(UserRole.DELIVERY_TEAM_LEAD, "OSG Team")
        session.add_all([second, first, inactive, another_team, wrong_role])
        await session.flush()
        session.add_all(
            [
                UserOrganisationMembership(
                    user_id=user.id,
                    unit_id=organisation_id(
                        "CEDAR_TEAM" if user is another_team else "OSG_TEAM"
                    ),
                )
                for user in [second, first, inactive, another_team, wrong_role]
            ]
        )
        await session.flush()

        actors = await SqlAlchemyWorkRepository(session).list_active_specialists(
            "OSG Team"
        )
        assert [actor.display_name for actor in actors] == [
            "Synthetic Alpha",
            "Synthetic Bravo",
        ]


@pytest.mark.asyncio
async def test_validate_completion_handles_present_and_missing_request(
    work_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = work_database
    async with factory() as session:
        worker, _, _, task = await seed_work(
            session,
            RequestStatus.TRIAGE_REVIEW,
            UserRole.INTAKE_TRIAGE,
            claimed=True,
        )
        repository = SqlAlchemyWorkRepository(session)
        bundle = await repository.get(task.id)
        assert bundle is not None
        payload = ProgressRequest(
            action="progress",
            category="Research",
            priority="LOW",
            destination_unit_id=uuid4(),
        )
        await repository.validate_completion(bundle.record, actor_from(worker), payload)
        missing_request = replace(
            bundle.record.request,
            id=uuid4(),
        )
        with pytest.raises(InvalidAction):
            await repository.validate_completion(
                replace(bundle.record, request=missing_request),
                actor_from(worker),
                payload,
            )


@pytest.mark.asyncio
async def test_nonterminal_completion_can_wait_for_reconciliation(
    work_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = work_database
    async with factory() as session:
        worker, request, instance, task = await seed_work(
            session,
            RequestStatus.TRIAGE_REVIEW,
            UserRole.INTAKE_TRIAGE,
            claimed=True,
        )
        repository = SqlAlchemyWorkRepository(session)
        task.status = WorkflowTaskStatus.COMPLETION_PENDING
        bundle = await repository.get(task.id)
        assert bundle is not None
        detail = await repository.apply_completion(
            bundle.record,
            actor_from(worker),
            ProgressRequest(
                action="progress",
                category="Research",
                priority="HIGH",
                destination_unit_id=uuid4(),
            ),
            next_task=None,
            reconciliation_needed=True,
        )
        assert detail.status is RequestStatus.COORDINATION_REVIEW
        assert request.workflow_error == "The next work item is being reconciled."
        assert instance.current_element_id is None
