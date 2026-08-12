"""Focused branch coverage for organisation queries and service policy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
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
from istari_service.errors import ObjectNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.organisation_models import (
    RequestRouteSelection,
    UserOrganisationMembership,
)
from istari_service.organisation_seed import organisation_id, seed_organisation_units
from istari_service.repositories.organisation import (
    SqlAlchemyOrganisationRepository,
    has_route_membership,
)
from istari_service.repositories.request_route_initialisation import (
    initialise_request_route,
)
from istari_service.services.organisation_service import (
    OrganisationRepository,
    OrganisationService,
)
from test_work_repository import actor_from, make_request, make_user


@pytest.fixture
async def organisation_database() -> AsyncIterator[
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
async def test_unit_listing_and_routing_options_include_empty_paths(
    organisation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = organisation_database
    async with factory() as session:
        await seed_organisation_units(session)
        requester = make_user(UserRole.REQUESTER, "Area A")
        session.add(requester)
        await session.flush()
        request = make_request(requester.id, RequestStatus.TRIAGE_REVIEW)
        session.add(request)
        await session.flush()
        repository = SqlAlchemyOrganisationRepository(session)

        units = await repository.list_units()
        assert len(units) == 40
        assert units[0].code == "CRIOC"
        assert (
            await repository.routing_options(request.id, RequestStatus.IN_PROGRESS)
            == []
        )
        assert (
            await repository.routing_options(request.id, RequestStatus.TRIAGE_REVIEW)
            == []
        )

        session.add(
            RequestRouteSelection(
                request_id=request.id,
                unit_id=organisation_id("CRIOC"),
                position=0,
            )
        )
        await session.flush()

        options = await repository.routing_options(
            request.id, RequestStatus.TRIAGE_REVIEW
        )
        assert [option.code for option in options] == ["JOCK", "SYGOC", "MYGOC"]
        workspace = await repository.routing_workspace(
            request.id, RequestStatus.TRIAGE_REVIEW
        )
        assert [(unit.name, unit.code) for unit in workspace.route] == [
            ("CRIOC", "CRIOC")
        ]
        assert [option.code for option in workspace.items] == [
            "JOCK",
            "SYGOC",
            "MYGOC",
        ]


@pytest.mark.asyncio
async def test_tracking_enforces_membership_and_maps_the_selected_route(
    organisation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = organisation_database
    async with factory() as session:
        await seed_organisation_units(session)
        requester = make_user(UserRole.REQUESTER, "Area A")
        triage_user = make_user(UserRole.INTAKE_TRIAGE, "Shared queue")
        session.add_all([requester, triage_user])
        await session.flush()
        request = make_request(requester.id, RequestStatus.COORDINATION_REVIEW)
        request.awaiting_team_staffing = True
        session.add(request)
        await session.flush()
        repository = SqlAlchemyOrganisationRepository(session)

        assert (await repository.page_tracked_requests(actor_from(requester)))[0] == []
        assert (await repository.page_tracked_requests(actor_from(triage_user)))[
            0
        ] == []

        session.add_all(
            [
                UserOrganisationMembership(
                    user_id=triage_user.id,
                    unit_id=organisation_id("CRIOC"),
                ),
                RequestRouteSelection(
                    request_id=request.id,
                    unit_id=organisation_id("CRIOC"),
                    position=0,
                ),
                RequestRouteSelection(
                    request_id=request.id,
                    unit_id=organisation_id("JOCK"),
                    position=1,
                ),
            ]
        )
        await session.flush()

        tracked, _cursor = await repository.page_tracked_requests(
            actor_from(triage_user, organisation_id("CRIOC"))
        )
        assert len(tracked) == 1
        assert tracked[0].id == request.id
        assert tracked[0].title == request.title
        assert tracked[0].awaiting_team_staffing is True
        assert [unit.name for unit in tracked[0].route] == ["CRIOC", "JOCK"]
        detail = await repository.get_tracked_request_detail(
            actor_from(triage_user, organisation_id("CRIOC")), request.id
        )
        assert detail is not None
        assert detail.description == request.description
        assert detail.requester_display_name == requester.display_name


@pytest.mark.asyncio
async def test_initial_route_requires_a_configured_root_and_adds_it(
    organisation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = organisation_database
    async with factory() as session:
        request_id = uuid4()
        with pytest.raises(RuntimeError, match="root is not configured"):
            await initialise_request_route(session, request_id)

        await seed_organisation_units(session)
        await initialise_request_route(session, request_id)

        selection = next(
            item for item in session.new if isinstance(item, RequestRouteSelection)
        )
        assert selection.request_id == request_id
        assert selection.unit_id == organisation_id("CRIOC")
        assert selection.position == 0


@pytest.mark.asyncio
async def test_organisation_service_hides_tracking_from_non_routing_roles() -> None:
    repository = AsyncMock(spec=OrganisationRepository)
    repository.list_units.return_value = []
    repository.page_tracked_requests.return_value = ([], None)
    repository.get_tracked_request_detail.return_value = object()
    service = OrganisationService(repository)
    requester = Actor(
        uuid4(),
        "requester@example.test",
        "Synthetic Requester",
        UserRole.REQUESTER,
        "Area A",
    )

    assert await service.list_units(requester) == []
    with pytest.raises(ObjectNotFound):
        await service.page_tracked_requests(requester)
    with pytest.raises(ObjectNotFound):
        await service.get_tracked_request_detail(requester, uuid4())
    repository.page_tracked_requests.assert_not_awaited()
    repository.get_tracked_request_detail.assert_not_awaited()

    triage_user = Actor(
        uuid4(),
        "triage@example.test",
        "Synthetic Triage User",
        UserRole.INTAKE_TRIAGE,
        "Shared queue",
        frozenset({uuid4()}),
    )
    assert await service.page_tracked_requests(triage_user) == ([], None)
    repository.page_tracked_requests.assert_awaited_once_with(
        triage_user,
        limit=50,
        cursor=None,
        search=None,
        statuses=(),
        current_owner=None,
        route_unit_id=None,
        minimum_age_days=None,
    )
    request_id = uuid4()
    assert await service.get_tracked_request_detail(triage_user, request_id) is not None
    repository.get_tracked_request_detail.assert_awaited_once_with(
        triage_user, request_id, event_limit=50, event_cursor=None
    )


@pytest.mark.asyncio
async def test_route_membership_handles_unscoped_roles_and_revocation() -> None:
    session = AsyncMock(spec=AsyncSession)
    requester = Actor(
        uuid4(),
        "requester@example.test",
        "Synthetic Requester",
        UserRole.REQUESTER,
        "Area A",
    )
    request_id = uuid4()

    assert await has_route_membership(session, requester, request_id) is True
    session.scalar.assert_not_awaited()

    triage_user = Actor(
        uuid4(),
        "triage@example.test",
        "Synthetic Triage User",
        UserRole.INTAKE_TRIAGE,
        "Shared queue",
        frozenset({uuid4()}),
    )
    session.scalar.side_effect = [uuid4(), None, None]
    assert await has_route_membership(session, triage_user, request_id) is True
    assert await has_route_membership(session, triage_user, request_id) is False
    assert (
        await has_route_membership(session, triage_user, request_id, lock=True) is False
    )
    locked_query = session.scalar.await_args_list[-1].args[0]
    assert locked_query._for_update_arg is not None
