"""Branch coverage for persisted human-work side effects."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.domain import Actor
from mist_service.errors import InvalidAction
from mist_service.models import (
    DeliverableStatus,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
)
from mist_service.organisation_seed import seed_organisation_units
from mist_service.qc_membership import QC_TEAM_ID
from mist_service.repositories.work_actions import (
    apply_work_effect,
    event_message,
    latest_deliverable,
    validate_work_effect,
)
from mist_service.schemas.work import (
    AllocateRequest,
    ApproveWork,
    AssignSpecialist,
    ChangesRequired,
    CompletionPayload,
    ProgressRequest,
    ProvideInformation,
    ReleaseDeliverable,
    RequestInformation,
    ResumeRequest,
    SendToAllocation,
    SubmitDeliverable,
)
from mist_service.team_models import TeamMembership, WorkspacePosition


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


def make_user(role: UserRole, scope: str) -> User:
    username = f"user.{uuid4().hex}@example.test"
    return User(
        username=username,
        email=username,
        display_name="Synthetic User",
        password_hash="$argon2id$synthetic",
        role=role,
        scope=scope,
    )


def make_request(requester_id: UUID) -> ServiceRequest:
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
        status=RequestStatus.QUALITY_REVIEW,
        current_owner="Quality and Release Team",
    )


def actor_from(user: User) -> Actor:
    return Actor(user.id, user.username, user.display_name, user.role, user.scope)


@pytest.mark.asyncio
async def test_validation_and_every_persisted_work_effect(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await seed_organisation_units(session)
        requester = make_user(UserRole.REQUESTER, "Area A")
        author = make_user(UserRole.DELIVERY_SPECIALIST, "DELIVERY_TEAM_A")
        reviewer = make_user(UserRole.QUALITY_RELEASE, "Shared queue")
        releaser = make_user(UserRole.QUALITY_RELEASE, "Shared queue")
        session.add_all([requester, author, reviewer, releaser])
        await session.flush()
        now = datetime.now(UTC)
        session.add_all(
            TeamMembership(
                user_id=user.id,
                team_id=QC_TEAM_ID,
                workspace_position=WorkspacePosition.MANAGER,
                effective_from=now,
                start_projected_at=now,
                start_reason="Synthetic QC test membership.",
            )
            for user in (reviewer, releaser)
        )
        await session.flush()
        request = make_request(requester.id)
        session.add(request)
        await session.flush()
        author_actor, reviewer_actor = actor_from(author), actor_from(reviewer)
        releaser_actor = actor_from(releaser)

        progress = ProgressRequest(
            action="progress",
            priority="HIGH",
            destination_unit_id=uuid4(),
        )
        assert await latest_deliverable(session, request.id) is None
        await validate_work_effect(session, request, reviewer_actor, progress)
        with pytest.raises(InvalidAction, match="deliverable is required"):
            await validate_work_effect(
                session, request, reviewer_actor, ApproveWork(action="approve")
            )
        with pytest.raises(InvalidAction):
            await apply_work_effect(
                session,
                request,
                reviewer_actor,
                ChangesRequired(action="changes_required", reason="Revise it."),
            )
        with pytest.raises(InvalidAction):
            await apply_work_effect(
                session, request, reviewer_actor, ApproveWork(action="approve")
            )
        with pytest.raises(InvalidAction):
            await apply_work_effect(
                session,
                request,
                reviewer_actor,
                ReleaseDeliverable(action="release", recipients=["Recipient"]),
            )

        await apply_work_effect(session, request, reviewer_actor, progress)
        assert request.triage_category is None
        assert request.priority == "HIGH"
        allocation = AllocateRequest(
            action="allocate",
            destination_unit_id=uuid4(),
            required_capabilities=["Writing"],
        )
        await apply_work_effect(session, request, reviewer_actor, allocation)
        await apply_work_effect(
            session,
            request,
            reviewer_actor,
            AssignSpecialist(
                action="assign",
                specialist_id=author.id,
                reason="The Manager selected the accountable delivery Lead.",
            ),
        )
        assert request.required_capabilities == ["Writing"]
        assert request.assigned_specialist_id == author.id

        submit = SubmitDeliverable(
            action="submit",
            deliverable_title="Synthetic response",
            deliverable_text="A sufficiently detailed synthetic response body.",
        )
        await apply_work_effect(session, request, author_actor, submit)
        await session.flush()
        await apply_work_effect(session, request, author_actor, submit)
        await session.flush()
        latest = await latest_deliverable(session, request.id)
        assert latest is not None and latest.version == 2
        with pytest.raises(InvalidAction, match="own work"):
            await validate_work_effect(
                session, request, author_actor, ApproveWork(action="approve")
            )
        with pytest.raises(InvalidAction):
            await apply_work_effect(
                session, request, author_actor, ApproveWork(action="approve")
            )

        changes = ChangesRequired(action="changes_required", reason="Revise it.")
        await apply_work_effect(session, request, reviewer_actor, changes)
        assert latest.status is DeliverableStatus.CHANGES_REQUIRED
        release = ReleaseDeliverable(action="release", recipients=["Recipient"])
        with pytest.raises(InvalidAction, match="approved deliverable"):
            await validate_work_effect(session, request, reviewer_actor, release)
        with pytest.raises(InvalidAction):
            await apply_work_effect(session, request, reviewer_actor, release)

        request.status = RequestStatus.LEAD_REVIEW
        await validate_work_effect(
            session, request, author_actor, ApproveWork(action="approve")
        )
        await apply_work_effect(
            session, request, author_actor, ApproveWork(action="approve")
        )
        request.status = RequestStatus.QUALITY_REVIEW
        await apply_work_effect(
            session, request, reviewer_actor, ApproveWork(action="approve")
        )
        assert latest.status is DeliverableStatus.APPROVED
        with pytest.raises(InvalidAction, match="QC reviewer cannot disseminate"):
            await validate_work_effect(session, request, reviewer_actor, release)
        await validate_work_effect(session, request, releaser_actor, release)
        await apply_work_effect(session, request, releaser_actor, release)
        assert latest.status is DeliverableStatus.RELEASED
        assert latest.release_recipients == ["Recipient"]
        assert latest.approved_at is not None and latest.released_at is not None


@pytest.mark.parametrize(
    ("payload", "status", "expected"),
    [
        (
            RequestInformation(action="request_information", reason="More context."),
            RequestStatus.TRIAGE_REVIEW,
            "Request information: More context.",
        ),
        (
            ProvideInformation(
                action="provide_information", information="New context."
            ),
            RequestStatus.INFORMATION_REQUIRED,
            "Information provided: New context.",
        ),
        (
            ResumeRequest(action="resume", note="Ready now."),
            RequestStatus.ON_HOLD,
            "Resume: Ready now.",
        ),
        (
            SendToAllocation(
                action="send_to_allocation",
                destination_unit_id=uuid4(),
                note="Route confirmed.",
            ),
            RequestStatus.COORDINATION_REVIEW,
            "Send to allocation: Route confirmed.",
        ),
        (
            ApproveWork(action="approve"),
            RequestStatus.QUALITY_REVIEW,
            "Deliverable approved for release.",
        ),
        (
            ApproveWork(action="approve"),
            RequestStatus.LEAD_REVIEW,
            "Deliverable sent for quality review.",
        ),
    ],
)
def test_event_messages(
    payload: CompletionPayload,
    status: RequestStatus,
    expected: str,
) -> None:
    assert event_message(payload, status) == expected


def test_event_message_unknown_action() -> None:
    class Unknown:
        action = "unknown"

    payload = cast(CompletionPayload, Unknown())
    assert event_message(payload, RequestStatus.ON_HOLD) == "Request updated."
