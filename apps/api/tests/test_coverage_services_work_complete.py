"""Work-service completion intent and error-mapping branches."""

from __future__ import annotations

from uuid import uuid4

import pytest

from istari_service.domain import Actor
from istari_service.errors import (
    InvalidAction,
    ObjectNotFound,
    WorkflowActionPending,
    WorkflowUnavailable,
)
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.schemas.work import (
    AssignSpecialist,
    ProgressRequest,
    ProvideInformation,
    WithdrawRequest,
)
from istari_service.services.work_service import WorkService
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowError,
    WorkflowTaskNotFound,
)
from test_coverage_services_work_claim import (
    FakeCommandDispatcher,
    FakeWorkRepository,
    actor,
    bundle,
)


def service_pair(
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    role: UserRole = UserRole.INTAKE_TRIAGE,
) -> tuple[WorkService, FakeWorkRepository, FakeCommandDispatcher, Actor]:
    user = actor(role)
    value = bundle(
        user,
        status=status,
        assignee_id=user.id,
        requester_id=user.id if role is UserRole.REQUESTER else None,
    )
    repository = FakeWorkRepository(value)
    dispatcher = FakeCommandDispatcher(repository)
    return WorkService(repository, dispatcher), repository, dispatcher, user


@pytest.mark.asyncio
async def test_complete_conceals_missing_and_rejects_invalid_states() -> None:
    triage = actor(UserRole.INTAKE_TRIAGE)
    repository = FakeWorkRepository()
    dispatcher = FakeCommandDispatcher(repository)
    service = WorkService(repository, dispatcher)
    progress = ProgressRequest(
        action="progress",
        priority="LOW",
        destination_unit_id=uuid4(),
    )
    with pytest.raises(ObjectNotFound):
        await service.complete(triage, uuid4(), progress)

    repository.value = bundle(triage, assignee_id=uuid4())
    with pytest.raises(ObjectNotFound):
        await service.complete(triage, repository.value.record.id, progress)
    repository.value = bundle(triage, assignee_id=triage.id)
    with pytest.raises(InvalidAction):
        await service.complete(
            triage,
            repository.value.record.id,
            ProvideInformation(action="provide_information", information="Context."),
        )
    repository.value = bundle(
        triage,
        assignee_id=triage.id,
        task_status=WorkflowTaskStatus.COMPLETION_PENDING,
    )
    with pytest.raises(WorkflowActionPending):
        await service.complete(triage, repository.value.record.id, progress)


@pytest.mark.asyncio
async def test_assignment_validation_rejects_invalid_specialists() -> None:
    lead = actor(UserRole.DELIVERY_TEAM_LEAD, scope="DELIVERY_TEAM_A")
    value = bundle(
        lead,
        status=RequestStatus.DELIVERY_PLANNING,
        assignee_id=lead.id,
        team="DELIVERY_TEAM_A",
    )
    repository = FakeWorkRepository(value)
    service = WorkService(repository, FakeCommandDispatcher(repository))
    await service._validate_assignment(
        value.record,
        ProgressRequest(
            action="progress",
            priority="LOW",
            destination_unit_id=uuid4(),
        ),
    )
    duplicate_assignment = uuid4()
    with pytest.raises(
        InvalidAction,
        match="Lead Analyst cannot also be a Contributor",
    ):
        await service._validate_assignment(
            value.record,
            AssignSpecialist(
                action="assign",
                specialist_id=duplicate_assignment,
                contributor_ids=[duplicate_assignment],
                reason="The same person cannot hold both assignment positions.",
            ),
        )
    payload = AssignSpecialist(
        action="assign",
        specialist_id=uuid4(),
        reason="The Manager selected the accountable delivery Lead.",
    )
    with pytest.raises(InvalidAction, match="active member of this team"):
        await service._validate_assignment(value.record, payload)
    repository.found_specialist = actor(UserRole.DELIVERY_TEAM_LEAD)
    with pytest.raises(InvalidAction):
        await service._validate_assignment(value.record, payload)
    repository.found_specialist = actor(
        UserRole.DELIVERY_SPECIALIST, scope="DELIVERY_TEAM_B"
    )
    with pytest.raises(InvalidAction):
        await service._validate_assignment(value.record, payload)
    repository.found_specialist = actor(
        UserRole.DELIVERY_SPECIALIST, scope="DELIVERY_TEAM_A"
    )
    await service._validate_assignment(value.record, payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (WorkflowEngineUnavailable("offline"), WorkflowUnavailable),
        (WorkflowConflict("complete", 409), InvalidAction),
        (WorkflowTaskNotFound("complete", 404), InvalidAction),
        (WorkflowError("invalid"), InvalidAction),
    ],
)
async def test_complete_maps_dispatch_failures_after_committed_intent(
    error: Exception,
    expected: type[Exception],
) -> None:
    service, repository, dispatcher, user = service_pair()
    dispatcher.error = error
    assert repository.value is not None
    with pytest.raises(expected):
        await service.complete(
            user,
            repository.value.record.id,
            ProgressRequest(
                action="progress",
                priority="HIGH",
                destination_unit_id=uuid4(),
            ),
        )
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_complete_returns_projected_detail_and_handles_missing_dispatch() -> None:
    service, repository, dispatcher, user = service_pair()
    assert repository.value is not None
    result = await service.complete(
        user,
        repository.value.record.id,
        ProgressRequest(
            action="progress",
            priority="HIGH",
            destination_unit_id=uuid4(),
        ),
    )
    assert result is repository.applied
    assert repository.pending_type == "complete"

    service, repository, dispatcher, user = service_pair(
        status=RequestStatus.INFORMATION_REQUIRED,
        role=UserRole.REQUESTER,
    )
    dispatcher.processed = False
    assert repository.value is not None
    with pytest.raises(WorkflowUnavailable):
        await service.complete(
            user,
            repository.value.record.id,
            WithdrawRequest(action="withdraw", reason="No longer required."),
        )
