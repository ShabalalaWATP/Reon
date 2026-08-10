"""Work projection queries and human-action persistence effects."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from istari_service.config import Environment, Settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from istari_service.models import (
    WorkflowTask as StoredTask,
)
from istari_service.organisation_models import (
    RequestRouteSelection,
    UserOrganisationMembership,
)
from istari_service.organisation_seed import organisation_id, seed_organisation_units
from istari_service.repositories.task_projection import next_task_projection
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.repositories.work_views import build_work_bundle
from istari_service.schemas.work import (
    ProgressRequest,
    WithdrawRequest,
)
from istari_service.team_models import TeamMembership
from istari_service.workflow.types import WorkflowTask, WorkflowTaskState


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


def make_user(role: UserRole, scope: str = "Shared queue") -> User:
    suffix = uuid4().hex
    return User(
        username=f"user.{suffix}@example.test",
        email=f"user.{suffix}@example.test",
        display_name=f"Synthetic {role.value.title()}",
        password_hash="$argon2id$synthetic",
        role=role,
        scope=scope,
    )


def actor_from(user: User, *organisation_unit_ids: UUID) -> Actor:
    return Actor(
        user.id,
        user.username,
        user.display_name,
        user.role,
        user.scope,
        frozenset(organisation_unit_ids),
    )


def make_request(requester_id: UUID, status: RequestStatus) -> ServiceRequest:
    return ServiceRequest(
        reference=f"SR-{uuid4().hex[:10].upper()}",
        requester_id=requester_id,
        title="Synthetic service request",
        service_category="Research",
        description="A sufficiently detailed synthetic request description.",
        question_to_answer="What does the synthetic evidence show?",
        desired_outcome="A useful fictional written response.",
        background_context="Synthetic context only.",
        subject_area_or_location="Synthetic subject area",
        coverage_start=datetime.now(UTC).date(),
        coverage_end=datetime.now(UTC).date() + timedelta(days=1),
        customer_urgency="ROUTINE",
        supported_activity_or_decision="A fictional planning decision.",
        required_by=datetime.now(UTC).date() + timedelta(days=7),
        required_by_reason="Needed for a fictional planning exercise.",
        preferred_deliverable_type="Plain text",
        success_criteria="The synthetic question is answered clearly.",
        constraints_or_caveats="No known constraints.",
        supporting_information="No supporting material is available.",
        sensitivity="STANDARD",
        handling_instructions="Retain synthetic content only.",
        status=status,
        current_owner="Synthetic owner",
    )


async def seed_work(
    session: AsyncSession,
    status: RequestStatus,
    role: UserRole,
    *,
    claimed: bool = False,
    process_key: str | None = "AUTO",
) -> tuple[User, ServiceRequest, WorkflowInstance, StoredTask]:
    await seed_organisation_units(session)
    requester = make_user(UserRole.REQUESTER, "Area A")
    worker = requester if role is UserRole.REQUESTER else make_user(role)
    session.add(requester)
    if worker is not requester:
        session.add(worker)
    await session.flush()
    request = make_request(requester.id, status)
    delivery_team_id = organisation_id("SSG_TEAM")
    if role is UserRole.DELIVERY_TEAM_LEAD:
        request.assigned_delivery_team = worker.scope
        request.assigned_delivery_team_id = delivery_team_id
    if role is UserRole.DELIVERY_SPECIALIST:
        request.assigned_delivery_team = worker.scope
        request.assigned_delivery_team_id = delivery_team_id
        request.assigned_specialist_id = worker.id
    session.add(request)
    await session.flush()
    route_codes = ["CRIOC", "JOCK", "ACSA_B_OPS", "SSG_TEAM"]
    session.add_all(
        [
            RequestRouteSelection(
                request_id=request.id,
                unit_id=organisation_id(code),
                position=position,
            )
            for position, code in enumerate(route_codes)
        ]
    )
    membership_position = {
        UserRole.INTAKE_TRIAGE: 0,
        UserRole.SERVICE_COORDINATION: 1,
        UserRole.OPERATIONS_ALLOCATION: 2,
        UserRole.DELIVERY_TEAM_LEAD: 3,
        UserRole.DELIVERY_SPECIALIST: 3,
    }.get(role)
    if role in {UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST}:
        now = datetime.now(UTC)
        session.add(
            TeamMembership(
                user_id=worker.id,
                team_id=delivery_team_id,
                effective_from=now,
                start_projected_at=now,
                start_reason="Synthetic test membership.",
            )
        )
    elif membership_position is not None:
        session.add(
            UserOrganisationMembership(
                user_id=worker.id,
                unit_id=organisation_id(route_codes[membership_position]),
            )
        )
    await session.flush()
    instance = WorkflowInstance(
        request_id=request.id,
        process_id="service-request-v1",
        process_instance_key=(
            f"process-{uuid4().hex}" if process_key == "AUTO" else process_key
        ),
        status=WorkflowInstanceStatus.ACTIVE,
    )
    session.add(instance)
    await session.flush()
    task = StoredTask(
        request_id=request.id,
        workflow_instance_id=instance.id,
        task_key=f"task-{uuid4().hex}",
        element_id=status.value.lower(),
        name=status.value.replace("_", " ").title(),
        candidate_role=role,
        expected_status=status,
        status=WorkflowTaskStatus.CLAIMED if claimed else WorkflowTaskStatus.OPEN,
        assignee_user_id=worker.id if claimed else None,
    )
    session.add(task)
    await session.flush()
    return worker, request, instance, task


@pytest.mark.asyncio
async def test_queue_get_claim_and_specialist_lookup(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        worker, _, _, task = await seed_work(
            session, RequestStatus.TRIAGE_REVIEW, UserRole.INTAKE_TRIAGE
        )
        _, hidden_request_row, hidden_instance_row, hidden = await seed_work(
            session,
            RequestStatus.TRIAGE_REVIEW,
            UserRole.INTAKE_TRIAGE,
            process_key=None,
        )
        _, _, _, completed = await seed_work(
            session, RequestStatus.TRIAGE_REVIEW, UserRole.INTAKE_TRIAGE
        )
        completed.status = WorkflowTaskStatus.COMPLETED
        repository = SqlAlchemyWorkRepository(session)
        actor = actor_from(worker, organisation_id("CRIOC"))
        bundles = await repository.list_for_actor(actor)
        assert [bundle.record.id for bundle in bundles] == [task.id]
        assert await repository.get(uuid4()) is None
        assert await repository.get(hidden.id) is None
        with pytest.raises(ValueError, match="process instance key"):
            build_work_bundle(hidden, hidden_request_row, hidden_instance_row)

        task.status = WorkflowTaskStatus.CLAIM_PENDING
        task.assignee_user_id = actor.id
        await session.flush()
        pending = await repository.get(task.id)
        assert pending is not None
        claimed = await repository.finalise_claim(pending.record, actor)
        assert claimed is not None
        assert claimed.assignee_id == worker.id
        assert claimed.available_actions == []
        session.expire(task, ["assignee"])
        refreshed = await repository.get(task.id)
        assert refreshed is not None
        assert "progress" in refreshed.view.available_actions
        assert await repository.finalise_claim(pending.record, actor) is None
        found = await repository.find_specialist(worker.id)
        assert found is not None and found.id == worker.id
        worker.is_active = False
        await session.flush()
        assert await repository.find_specialist(worker.id) is None
        assert await repository.find_specialist(uuid4()) is None


@pytest.mark.asyncio
async def test_apply_completion_projects_next_and_terminal_stages(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
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
        next_task = WorkflowTask(
            task_key="coordination-task",
            process_instance_key="process-key",
            element_id="coordination_review",
            state=WorkflowTaskState.CREATED,
        )
        detail = await repository.apply_completion(
            bundle.record,
            actor_from(worker, organisation_id("CRIOC")),
            ProgressRequest(
                action="progress",
                priority="MEDIUM",
                destination_unit_id=uuid4(),
            ),
            next_task=next_task,
            reconciliation_needed=False,
        )
        assert detail.status is RequestStatus.COORDINATION_REVIEW
        assert request.version == 2
        assert instance.current_element_id == "coordination_review"
        projected = await session.scalar(
            select(StoredTask).where(StoredTask.task_key == "coordination-task")
        )
        assert projected is not None and projected.status is WorkflowTaskStatus.OPEN
        with pytest.raises(InvalidAction):
            await repository.apply_completion(
                bundle.record,
                actor_from(worker, organisation_id("CRIOC")),
                ProgressRequest(
                    action="progress",
                    priority="LOW",
                    destination_unit_id=uuid4(),
                ),
                next_task=None,
                reconciliation_needed=True,
            )

        requester, _terminal, terminal_instance, terminal_task = await seed_work(
            session,
            RequestStatus.INFORMATION_REQUIRED,
            UserRole.REQUESTER,
            claimed=True,
        )
        terminal_task.status = WorkflowTaskStatus.COMPLETION_PENDING
        terminal_bundle = await repository.get(terminal_task.id)
        assert terminal_bundle is not None
        result = await repository.apply_completion(
            terminal_bundle.record,
            actor_from(requester),
            WithdrawRequest(action="withdraw", reason="No longer required."),
            next_task=None,
            reconciliation_needed=False,
        )
        assert result.status is RequestStatus.CANCELLED
        assert terminal_instance.status is WorkflowInstanceStatus.COMPLETED
        assert terminal_instance.completed_at is not None

        invalid_assignee = WorkflowTask(
            task_key="invalid-assignee",
            process_instance_key="process-key",
            element_id="coordination_review",
            state=WorkflowTaskState.CREATED,
            assignee="not-a-uuid",
        )
        projection = next_task_projection(request, instance, invalid_assignee)
        assert projection.assignee_user_id is None
        valid_assignee = replace(invalid_assignee, assignee=str(worker.id))
        claimed_projection = next_task_projection(request, instance, valid_assignee)
        assert claimed_projection.status is WorkflowTaskStatus.CLAIMED
