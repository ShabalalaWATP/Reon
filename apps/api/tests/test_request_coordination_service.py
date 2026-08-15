"""Security and audit behaviour for request coordination."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.errors import InvalidAction, ObjectNotFound
from mist_service.models import RequestStatus, UserRole
from mist_service.organisation_models import (
    RequestRouteSelection,
    UserOrganisationMembership,
)
from mist_service.organisation_seed import organisation_id, seed_organisation_units
from mist_service.repositories.request_views import build_request_detail
from mist_service.request_coordination_composition import (
    request_coordination_service,
)
from mist_service.schemas.coordination import (
    CoordinationAudience,
    CoordinationMessageCreate,
    ReturnRequestCreate,
)
from mist_service.team_models import TeamMembership, WorkspacePosition
from test_work_repository import actor_from, make_request, make_user


@pytest.fixture
async def coordination_database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
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
        request = make_request(customer.id, RequestStatus.TRIAGE_REVIEW)
        session.add(request)
        await session.flush()
        crioc_id = organisation_id("CRIOC")
        session.add_all(
            [
                UserOrganisationMembership(user_id=triage.id, unit_id=crioc_id),
                TeamMembership(
                    user_id=triage.id,
                    team_id=crioc_id,
                    workspace_position=WorkspacePosition.MANAGER,
                    effective_from=datetime.now(UTC),
                    started_by_user_id=triage.id,
                    start_reason="Synthetic current route membership.",
                ),
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
        service = request_coordination_service(session)

        with pytest.raises(ObjectNotFound):
            await service.post_message(
                actor_from(customer),
                uuid4(),
                CoordinationMessageCreate(
                    audience=CoordinationAudience.CURRENT_OWNER,
                    body="An unknown request must not disclose its existence.",
                    client_mutation_id=uuid4(),
                ),
            )

        question_body = "Can the Customer confirm the synthetic priority?"
        question_command = CoordinationMessageCreate(
            audience=CoordinationAudience.CUSTOMER,
            body=question_body,
            client_mutation_id=uuid4(),
        )
        question = await service.post_message(
            actor_from(triage, crioc_id),
            request.id,
            question_command,
        )
        assert question.type == "COORDINATION_MESSAGE"
        assert question.message == "Question for Customer recorded."
        repeated = await service.post_message(
            actor_from(triage, crioc_id), request.id, question_command
        )
        assert repeated.id == question.id

        response_body = "The synthetic priority remains unchanged."
        response = await service.post_message(
            actor_from(customer),
            request.id,
            CoordinationMessageCreate(
                audience=CoordinationAudience.CURRENT_OWNER,
                body=response_body,
                client_mutation_id=uuid4(),
            ),
        )
        assert response.message == "Message for current owner recorded."
        assert request.audit_event_count == 2
        customer_detail = await build_request_detail(
            session,
            request.id,
            reveal_unreleased_deliverable=False,
            include_staff_events=False,
        )
        staff_detail = await build_request_detail(
            session,
            request.id,
            reveal_unreleased_deliverable=True,
            include_staff_events=True,
        )
        assert [event.message for event in customer_detail.events] == [question.message]
        assert [event.message for event in staff_detail.events] == [
            question.message,
            response.message,
        ]
        assert question_body not in " ".join(
            event.message for event in staff_detail.events
        )
        assert response_body not in " ".join(
            event.message for event in staff_detail.events
        )


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
        service = request_coordination_service(session)
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
                    client_mutation_id=uuid4(),
                ),
            )
