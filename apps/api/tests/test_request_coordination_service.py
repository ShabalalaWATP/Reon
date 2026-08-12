"""Security and audit behaviour for request coordination."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.errors import InvalidAction, ObjectNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.organisation_models import (
    RequestRouteSelection,
    UserOrganisationMembership,
)
from istari_service.organisation_seed import organisation_id, seed_organisation_units
from istari_service.schemas.coordination import (
    CoordinationAudience,
    CoordinationMessageCreate,
    ReturnRequestCreate,
)
from istari_service.services.request_coordination_service import (
    RequestCoordinationService,
)
from test_work_repository import actor_from, make_request, make_user


@pytest.fixture
async def coordination_database() -> AsyncIterator[
    async_sessionmaker[AsyncSession]
]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_route_user_and_customer_can_record_coordination(
    coordination_database: async_sessionmaker[AsyncSession],
) -> None:
    async with coordination_database() as session:
        await seed_organisation_units(session)
        customer = make_user(UserRole.REQUESTER, "Customer")
        triage = make_user(UserRole.INTAKE_TRIAGE, "CRIOC")
        session.add_all([customer, triage])
        await session.flush()
        request = make_request(customer.id, RequestStatus.IN_PROGRESS)
        session.add(request)
        await session.flush()
        crioc_id = organisation_id("CRIOC")
        session.add_all(
            [
                UserOrganisationMembership(user_id=triage.id, unit_id=crioc_id),
                RequestRouteSelection(
                    request_id=request.id, unit_id=crioc_id, position=0
                ),
                RequestRouteSelection(
                    request_id=request.id,
                    unit_id=organisation_id("JOCK"),
                    position=1,
                ),
            ]
        )
        await session.flush()
        service = RequestCoordinationService(session)

        with pytest.raises(ObjectNotFound):
            await service.post_message(
                actor_from(customer),
                uuid4(),
                CoordinationMessageCreate(
                    audience=CoordinationAudience.CURRENT_OWNER,
                    body="An unknown request must not disclose its existence.",
                ),
            )

        question = await service.post_message(
            actor_from(triage, crioc_id),
            request.id,
            CoordinationMessageCreate(
                audience=CoordinationAudience.CUSTOMER,
                body="Can the Customer confirm the synthetic priority?",
            ),
        )
        assert question.type == "COORDINATION_MESSAGE"
        assert question.message.startswith("Question for Customer:")

        response = await service.post_message(
            actor_from(customer),
            request.id,
            CoordinationMessageCreate(
                audience=CoordinationAudience.CURRENT_OWNER,
                body="The synthetic priority remains unchanged.",
            ),
        )
        assert response.message.startswith("Message for current owner:")
        assert request.audit_event_count == 2


@pytest.mark.asyncio
async def test_return_requests_are_route_scoped_and_target_earlier_units(
    coordination_database: async_sessionmaker[AsyncSession],
) -> None:
    async with coordination_database() as session:
        await seed_organisation_units(session)
        customer = make_user(UserRole.REQUESTER, "Customer")
        triage = make_user(UserRole.INTAKE_TRIAGE, "CRIOC")
        outsider = make_user(UserRole.INTAKE_TRIAGE, "Other")
        session.add_all([customer, triage, outsider])
        await session.flush()
        request = make_request(customer.id, RequestStatus.IN_PROGRESS)
        session.add(request)
        await session.flush()
        crioc_id = organisation_id("CRIOC")
        session.add_all(
            [
                UserOrganisationMembership(user_id=triage.id, unit_id=crioc_id),
                RequestRouteSelection(
                    request_id=request.id, unit_id=crioc_id, position=0
                ),
                RequestRouteSelection(
                    request_id=request.id,
                    unit_id=organisation_id("JOCK"),
                    position=1,
                ),
            ]
        )
        await session.flush()
        service = RequestCoordinationService(session)
        event = await service.request_return(
            actor_from(triage, crioc_id),
            request.id,
            ReturnRequestCreate(
                target_unit_id=crioc_id,
                reason="CRIOC needs to reconsider the original routing decision.",
            ),
        )
        assert event.type == "OWNERSHIP_RETURN_REQUESTED"
        with pytest.raises(ObjectNotFound):
            await service.request_return(
                actor_from(customer),
                request.id,
                ReturnRequestCreate(
                    target_unit_id=crioc_id,
                    reason="Customers cannot initiate internal ownership returns.",
                ),
            )
        for target_id in (uuid4(), organisation_id("JOCK")):
            with pytest.raises(InvalidAction):
                await service.request_return(
                    actor_from(triage, crioc_id),
                    request.id,
                    ReturnRequestCreate(
                        target_unit_id=target_id,
                        reason="This target is not an earlier authorised route unit.",
                    ),
                )
        request.status = RequestStatus.CANCELLED
        with pytest.raises(InvalidAction):
            await service.request_return(
                actor_from(triage, crioc_id),
                request.id,
                ReturnRequestCreate(
                    target_unit_id=crioc_id,
                    reason="Closed work cannot be returned into active routing.",
                ),
            )
        with pytest.raises(ObjectNotFound):
            await service.request_return(
                actor_from(make_user(UserRole.PLATFORM_ADMIN, "Platform")),
                request.id,
                ReturnRequestCreate(
                    target_unit_id=crioc_id,
                    reason="Administrators cannot read or route request content.",
                ),
            )
        with pytest.raises(ObjectNotFound):
            await service.request_return(
                actor_from(outsider),
                request.id,
                ReturnRequestCreate(
                    target_unit_id=crioc_id,
                    reason="This user is not on the immutable selected route.",
                ),
            )
        with pytest.raises(InvalidAction):
            await service.post_message(
                actor_from(customer),
                request.id,
                CoordinationMessageCreate(
                    audience=CoordinationAudience.CUSTOMER,
                    body="Customers cannot address themselves through this endpoint.",
                ),
            )
