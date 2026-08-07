"""Persistence-model invariants against the portable SQLite mapping."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.models import (
    Base,
    Deliverable,
    DeliverableStatus,
    Feedback,
    OutboxStatus,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    Session,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
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
    yield engine, create_session_factory(engine)
    await engine.dispose()


def make_user(*, role: UserRole = UserRole.REQUESTER) -> User:
    suffix = uuid4().hex
    return User(
        username=f"user.{suffix}@example.test",
        display_name="Synthetic User",
        password_hash="$argon2id$synthetic",
        role=role,
        scope="DELIVERY_TEAM_A" if role != UserRole.REQUESTER else "Area A",
    )


def make_request(requester_id: UUID, *, reference: str | None = None) -> ServiceRequest:
    return ServiceRequest(
        reference=reference or f"SR-{uuid4().hex[:10].upper()}",
        requester_id=requester_id,
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
async def test_all_models_persist_with_defaults_and_relationships(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user()
        specialist = make_user(role=UserRole.DELIVERY_SPECIALIST)
        session.add_all([requester, specialist])
        await session.flush()
        request = make_request(requester.id)
        request.assigned_specialist_id = specialist.id
        session.add(request)
        await session.flush()
        instance = WorkflowInstance(
            request_id=request.id,
            process_id="service-request-v1",
            process_definition_key="definition-key",
            process_version=1,
            process_instance_key="instance-key",
        )
        login = Session(
            user_id=requester.id,
            token_hash="1" * 64,
            csrf_token_hash="2" * 64,
            credential_version=1,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add_all([instance, login])
        await session.flush()
        task = WorkflowTask(
            request_id=request.id,
            workflow_instance_id=instance.id,
            task_key="task-key",
            element_id="intake_review",
            name="Intake review",
            candidate_role=UserRole.INTAKE_TRIAGE,
            expected_status=RequestStatus.ROUTING_PENDING,
        )
        event = RequestEvent(
            request_id=request.id,
            actor_user_id=requester.id,
            type="request_submitted",
            message="Request submitted.",
            prior_status=None,
            next_status=RequestStatus.ROUTING_PENDING,
            event_hash="3" * 64,
        )
        deliverable = Deliverable(
            request_id=request.id,
            version=1,
            title="Synthetic response",
            text="Synthetic response body.",
            author_user_id=specialist.id,
        )
        feedback = Feedback(
            request_id=request.id,
            requester_id=requester.id,
            rating=5,
            comments="Very useful.",
        )
        outbox = WorkflowOutbox(
            request_id=request.id,
            event_type="START_PROCESS",
            payload={"requestId": str(request.id)},
            idempotency_key=f"start:{request.id}",
        )
        session.add_all([task, event, deliverable, feedback, outbox])
        await session.commit()

    async with factory() as session:
        stored = await session.scalar(
            select(ServiceRequest).options(
                selectinload(ServiceRequest.requester),
                selectinload(ServiceRequest.assigned_specialist),
            )
        )
        assert stored is not None
        assert stored.status is RequestStatus.ROUTING_PENDING
        assert stored.current_owner == "Intake & Triage Team"
        assert stored.version == 1
        assert stored.requester.username == requester.username
        assert stored.assigned_specialist is not None
        stored_task = await session.scalar(select(WorkflowTask))
        stored_outbox = await session.scalar(select(WorkflowOutbox))
        stored_deliverable = await session.scalar(select(Deliverable))
        stored_instance = await session.scalar(select(WorkflowInstance))
        assert stored_task is not None
        assert stored_task.status is WorkflowTaskStatus.OPEN
        assert stored_outbox is not None
        assert stored_outbox.status is OutboxStatus.PENDING
        assert stored_outbox.attempts == 0
        assert stored_deliverable is not None
        assert stored_deliverable.status is DeliverableStatus.SUBMITTED
        assert stored_instance is not None
        assert stored_instance.status is WorkflowInstanceStatus.START_PENDING


@pytest.mark.asyncio
async def test_submitted_form_is_immutable_but_projection_can_change(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user()
        session.add(requester)
        await session.flush()
        request = make_request(requester.id)
        session.add(request)
        await session.commit()
        request_id = request.id

    async with factory() as session:
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.TRIAGE_REVIEW
        await session.commit()

    async with factory() as session:
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.title = "An impermissible replacement"
        with pytest.raises(ValueError, match="immutable"):
            await session.flush()


@pytest.mark.asyncio
async def test_event_and_feedback_are_append_only(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user()
        session.add(requester)
        await session.flush()
        request = make_request(requester.id)
        session.add(request)
        await session.flush()
        event = RequestEvent(
            request_id=request.id,
            actor_user_id=requester.id,
            type="created",
            message="Created.",
            details={},
            event_hash="4" * 64,
        )
        feedback = Feedback(
            request_id=request.id,
            requester_id=requester.id,
            rating=4,
            comments="Synthetic feedback.",
        )
        session.add_all([event, feedback])
        await session.commit()
        event_id, feedback_id = event.id, feedback.id

    async with factory() as session:
        event = await session.get(RequestEvent, event_id)
        assert event is not None
        event.message = "Changed."
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()

    async with factory() as session:
        feedback = await session.get(Feedback, feedback_id)
        assert feedback is not None
        await session.delete(feedback)
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()


@pytest.mark.asyncio
async def test_relational_constraints_reject_invalid_or_duplicate_rows(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        requester = make_user()
        session.add(requester)
        await session.flush()
        request = make_request(requester.id)
        session.add(request)
        await session.flush()
        session.add(
            Feedback(request_id=request.id, requester_id=requester.id, rating=0)
        )
        with pytest.raises(IntegrityError):
            await session.flush()

    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "service_requests",
        "request_events",
        "workflow_instances",
        "workflow_tasks",
        "deliverables",
        "feedback",
        "workflow_outbox",
        "organisation_units",
        "request_route_selections",
        "user_organisation_memberships",
        "admin_audit_anchors",
        "admin_audit_events",
        "admin_identity_sequences",
        "request_drafts",
        "clarification_threads",
        "clarification_messages",
        "organisation_closure",
        "management_grants",
        "management_grant_actions",
        "request_analytics_facts",
        "request_stage_intervals",
        "analytics_projection_state",
        "team_memberships",
        "team_activity_events",
        "calendar_events",
        "calendar_occurrence_exceptions",
        "calendar_capacity_previews",
        "calendar_capacity_snapshots",
        "team_iterations",
        "work_packages",
        "work_package_contributors",
        "work_package_dependencies",
        "work_package_activity",
        "capacity_reservations",
        "team_board_configurations",
        "saved_board_views",
        "request_links",
        "operational_runs",
    }
    assert {role.value for role in UserRole} >= {
        "PLATFORM_ADMIN",
        "REQUESTER",
        "QUALITY_RELEASE",
    }
