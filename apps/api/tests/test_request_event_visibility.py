"""Customer-visible request history pagination."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.models import RequestStatus, UserRole
from mist_service.organisation_seed import seed_organisation_units
from mist_service.repositories.event_store import append_request_event
from mist_service.request_event_audience import RequestEventAudience
from synthetic_user_support import make_user
from test_request_repository import create_request


@pytest.fixture
async def request_database() -> AsyncIterator[
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


async def test_customer_event_cursor_pages_only_customer_visible_history(
    request_database,
) -> None:
    _, factory = request_database
    async with factory() as session:
        requester = make_user(UserRole.REQUESTER)
        session.add(requester)
        await session.flush()
        repository, request_id = await create_request(session, requester)
        await append_request_event(
            session,
            request_id=request_id,
            actor_id=requester.id,
            event_type="future_internal_event",
            message="A newly introduced event is internal by default.",
            prior_status=RequestStatus.ROUTING_PENDING,
            next_status=RequestStatus.ROUTING_PENDING,
        )
        await append_request_event(
            session,
            request_id=request_id,
            actor_id=requester.id,
            event_type="customer_update",
            message="Customer-visible update.",
            audience=RequestEventAudience.CUSTOMER_AND_STAFF,
            prior_status=RequestStatus.ROUTING_PENDING,
            next_status=RequestStatus.ROUTING_PENDING,
        )
        first = await repository.get_detail(
            request_id,
            reveal_unreleased_deliverable=False,
            include_staff_events=False,
            event_limit=1,
        )
        assert [event.message for event in first.events] == ["Customer-visible update."]
        assert first.events_next_cursor is not None
        second = await repository.get_detail(
            request_id,
            reveal_unreleased_deliverable=False,
            include_staff_events=False,
            event_limit=1,
            event_cursor=first.events_next_cursor,
        )
        assert [event.type for event in second.events] == ["request_submitted"]
        assert second.events_next_cursor is None


async def test_repository_detail_hides_staff_events_by_default(
    request_database,
) -> None:
    _, factory = request_database
    async with factory() as session:
        requester = make_user(UserRole.REQUESTER)
        session.add(requester)
        await session.flush()
        repository, request_id = await create_request(session, requester)
        await append_request_event(
            session,
            request_id=request_id,
            actor_id=requester.id,
            event_type="future_internal_event",
            message="Internal detail.",
            prior_status=RequestStatus.ROUTING_PENDING,
            next_status=RequestStatus.ROUTING_PENDING,
        )
        default_detail = await repository.get_detail(
            request_id,
            reveal_unreleased_deliverable=False,
        )
        staff_detail = await repository.get_detail(
            request_id,
            reveal_unreleased_deliverable=True,
            include_staff_events=True,
        )
        assert "future_internal_event" not in {
            event.type for event in default_detail.events
        }
        assert "future_internal_event" in {event.type for event in staff_detail.events}
