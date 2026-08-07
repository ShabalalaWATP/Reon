"""Requester persistence, read-model and audit-chain behaviour."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from istari_service.audit import canonical_event_hash, verify_event_chain
from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.errors import FeedbackUnavailable
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowOutbox,
)
from istari_service.organisation_seed import seed_organisation_units
from istari_service.repositories.event_store import (
    append_request_event,
    audit_key_for_session,
)
from istari_service.repositories.request_views import build_request_detail
from istari_service.repositories.requests import SqlAlchemyRequestRepository
from istari_service.schemas.requests import FeedbackCreate, RequestCreate, Sensitivity
from pin_test_support import StaticConfigurationPins
from synthetic_user_support import actor_from, make_user


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


def request_command() -> RequestCreate:
    return RequestCreate(
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
        sensitivity=Sensitivity.STANDARD,
        handling_instructions="Retain synthetic content only.",
    )


async def create_request(
    session: AsyncSession,
    requester: User,
) -> tuple[SqlAlchemyRequestRepository, UUID]:
    repository = SqlAlchemyRequestRepository(
        session,
        process_id="service-request-v1",
        configuration_pins=StaticConfigurationPins(),  # type: ignore[arg-type]
    )
    detail = await repository.create(actor_from(requester), request_command())
    return repository, detail.id


@pytest.mark.asyncio
async def test_create_list_get_and_hash_linked_events(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user(UserRole.REQUESTER)
        other = make_user(UserRole.REQUESTER)
        session.add_all([requester, other])
        await session.flush()
        repository, request_id = await create_request(session, requester)
        detail = await repository.get_detail(
            request_id, reveal_unreleased_deliverable=False
        )
        assert detail.reference.startswith(f"SR-{datetime.now(UTC).year}-")
        assert detail.requester.id == requester.id
        assert detail.events[0].actor_display_name == requester.display_name
        assert detail.deliverable is None
        assert detail.feedback is None
        assert detail.assigned_specialist is None

        owned = await repository.list_for_requester(requester.id)
        assert [item.id for item in owned] == [request_id]
        assert await repository.list_for_requester(other.id) == []
        record = await repository.get_record_for_actor(
            request_id, actor_from(requester)
        )
        assert record is not None and record.version == 1
        assert (
            await repository.get_record_for_actor(uuid4(), actor_from(requester))
            is None
        )
        outbox = await session.scalar(select(WorkflowOutbox))
        instance = await session.scalar(select(WorkflowInstance))
        assert outbox is not None
        assert outbox.payload == {
            "requestId": str(request_id),
            "requesterId": str(requester.id),
            "processId": "service-request-v1",
            "processVersion": 1,
            "processChecksum": "a" * 64,
        }
        assert instance is not None and instance.process_id == "service-request-v1"
        assert instance.process_version == 1
        assert instance.process_checksum == "a" * 64

        second = await append_request_event(
            session,
            request_id=request_id,
            actor_id=None,
            event_type="system_reconciled",
            message="Projection reconciled.",
            prior_status=RequestStatus.ROUTING_PENDING,
            next_status=RequestStatus.ROUTING_PENDING,
            details={"attempt": 1},
        )
        assert second.previous_hash is not None
        events = (
            await session.scalars(
                select(RequestEvent)
                .where(RequestEvent.request_id == request_id)
                .order_by(RequestEvent.created_at, RequestEvent.id)
            )
        ).all()
        chain = [
            {
                "request_id": event.request_id,
                "event_type": event.type,
                "message": event.message,
                "actor_id": event.actor_user_id,
                "created_at": event.created_at,
                "previous_hash": event.previous_hash,
                "prior_status": event.prior_status,
                "next_status": event.next_status,
                "details": event.details,
                "event_hash": event.event_hash,
            }
            for event in events
        ]
        anchored = await session.get(ServiceRequest, request_id)
        assert anchored is not None
        assert anchored.audit_event_count == 2
        assert anchored.audit_head_hash == events[-1].event_hash
        assert anchored.audit_anchor_mac is not None
        audit_key = audit_key_for_session(session)
        assert verify_event_chain(
            chain,
            audit_key=audit_key,
            expected_head_hash=anchored.audit_head_hash,
            expected_count=anchored.audit_event_count,
        )
        assert verify_event_chain([], audit_key=audit_key)
        bad_previous = [dict(item) for item in chain]
        bad_previous[1]["previous_hash"] = "f" * 64
        assert not verify_event_chain(bad_previous, audit_key=audit_key)
        bad_hash = [dict(item) for item in chain]
        bad_hash[0]["event_hash"] = "f" * 64
        assert not verify_event_chain(bad_hash, audit_key=audit_key)
        bad_status = [dict(item) for item in chain]
        bad_status[1]["next_status"] = RequestStatus.COMPLETED
        assert not verify_event_chain(bad_status, audit_key=audit_key)
        assert not verify_event_chain(
            chain[:-1],
            audit_key=audit_key,
            expected_head_hash=anchored.audit_head_hash,
            expected_count=anchored.audit_event_count,
        )

    naive_time = datetime(2026, 8, 6, 12, 0)  # noqa: DTZ001
    assert canonical_event_hash(
        request_id=request_id,
        event_type="synthetic",
        message="Synthetic event.",
        actor_id=None,
        created_at=naive_time,
        previous_hash=None,
        audit_key=b"a" * 32,
    ) == canonical_event_hash(
        request_id=request_id,
        event_type="synthetic",
        message="Synthetic event.",
        actor_id=None,
        created_at=naive_time.replace(tzinfo=UTC),
        previous_hash=None,
        audit_key=b"a" * 32,
        details={},
    )


@pytest.mark.asyncio
async def test_request_detail_controls_deliverable_visibility(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user(UserRole.REQUESTER)
        specialist = make_user(
            UserRole.DELIVERY_SPECIALIST,
            scope="DELIVERY_TEAM_A",
        )
        session.add_all([requester, specialist])
        await session.flush()
        repository, request_id = await create_request(session, requester)
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.assigned_delivery_team = "DELIVERY_TEAM_A"
        request.assigned_specialist_id = specialist.id
        request.status = RequestStatus.INFORMATION_REQUIRED
        request.workflow_error = "Synthetic reconciliation warning."
        submitted = Deliverable(
            request_id=request_id,
            version=1,
            title="Submitted response",
            text="This response has not been released.",
            author_user_id=specialist.id,
        )
        session.add(submitted)
        await session.flush()
        hidden = await repository.get_detail(
            request_id, reveal_unreleased_deliverable=False
        )
        visible = await repository.get_detail(
            request_id, reveal_unreleased_deliverable=True
        )
        assert hidden.deliverable is None
        assert visible.deliverable is not None
        assert visible.deliverable.title == "Submitted response"

        released = Deliverable(
            request_id=request_id,
            version=2,
            title="Released response",
            text="This synthetic response is released.",
            author_user_id=specialist.id,
            status=DeliverableStatus.RELEASED,
            released_at=datetime.now(UTC),
        )
        feedback = Feedback(
            request_id=request_id,
            requester_id=requester.id,
            rating=5,
            comments="Useful synthetic response.",
        )
        session.add_all([released, feedback])
        request.status = RequestStatus.COMPLETED
        await append_request_event(
            session,
            request_id=request_id,
            actor_id=None,
            event_type="projection_updated",
            message="Projection updated.",
            prior_status=RequestStatus.ROUTING_PENDING,
            next_status=RequestStatus.INFORMATION_REQUIRED,
        )
        await session.flush()
        detail = await repository.get_detail(
            request_id, reveal_unreleased_deliverable=False
        )
        assert detail.deliverable is not None
        assert detail.deliverable.title == "Released response"
        assert detail.feedback is not None and detail.feedback.rating == 5
        assert detail.assigned_specialist is not None
        assert detail.assigned_specialist.id == specialist.id
        assert detail.events[-1].actor_display_name is None
        assert detail.workflow_error is not None
        assert detail.product_available
        summaries = await repository.list_for_requester(requester.id)
        assert summaries[0].product_available
        assert not summaries[0].needs_requester_input


@pytest.mark.asyncio
async def test_feedback_gates_and_missing_detail(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user(UserRole.REQUESTER)
        session.add(requester)
        await session.flush()
        repository, request_id = await create_request(session, requester)
        actor = actor_from(requester)
        command = FeedbackCreate(rating=4, comments="Synthetic feedback.")
        assert not await repository.feedback_exists(request_id)
        with pytest.raises(FeedbackUnavailable):
            await repository.add_feedback(uuid4(), actor, command)
        with pytest.raises(FeedbackUnavailable):
            await repository.add_feedback(request_id, actor, command)
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.COMPLETED
        view = await repository.add_feedback(request_id, actor, command)
        assert view.rating == 4
        assert await repository.feedback_exists(request_id)
        repeated = await repository.add_feedback(request_id, actor, command)
        assert repeated.id == view.id
        with pytest.raises(FeedbackUnavailable):
            await repository.add_feedback(
                request_id,
                actor,
                FeedbackCreate(rating=4, comments="A separate attempt."),
            )
        with pytest.raises(LookupError, match="no longer exists"):
            await build_request_detail(
                session,
                uuid4(),
                reveal_unreleased_deliverable=False,
            )
        feedback_event = await session.scalar(
            select(RequestEvent).where(RequestEvent.type == "feedback_submitted")
        )
        assert feedback_event is not None
        assert feedback_event.actor_user_id == requester.id
