"""Work-service visibility, specialist and claim branches."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mist_service.domain import Actor, RequestRecord, WorkRecord
from mist_service.errors import (
    AlreadyClaimed,
    InvalidAction,
    ObjectNotFound,
    WorkflowActionPending,
    WorkflowUnavailable,
)
from mist_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from mist_service.schemas.work import CompletionPayload, WorkItem
from mist_service.services.work_service import WorkService
from mist_service.work_types import WorkBundle
from mist_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowError,
)


def actor(
    role: UserRole,
    *,
    user_id: UUID | None = None,
    scope: str = "Shared queue",
) -> Actor:
    return Actor(
        user_id or uuid4(),
        f"{role.value.lower()}@example.test",
        "Synthetic User",
        role,
        scope,
    )


def bundle(
    _user: Actor,
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    assignee_id: UUID | None = None,
    completed: bool = False,
    engine_key: str | None = "task-key",
    requester_id: UUID | None = None,
    team: str | None = None,
    specialist_id: UUID | None = None,
    task_status: WorkflowTaskStatus | None = None,
) -> WorkBundle:
    request = RequestRecord(
        uuid4(),
        requester_id or uuid4(),
        status,
        team,
        specialist_id,
        1,
    )
    resolved_status = task_status or (
        WorkflowTaskStatus.CLAIMED if assignee_id else WorkflowTaskStatus.OPEN
    )
    record = WorkRecord(
        uuid4(),
        request,
        engine_key,
        "process-key",
        status.value.lower(),
        resolved_status,
        assignee_id,
        datetime.now(UTC) if completed else None,
    )
    view = WorkItem(
        id=record.id,
        request_id=request.id,
        request_reference="SR-SYNTHETIC",
        request_version=request.version,
        title="Synthetic service request",
        stage=status,
        status=resolved_status.value,
        assignee_id=assignee_id,
        assignee_display_name=None,
        delivery_team=team,
        available_actions=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return WorkBundle(record, view)


class FakeWorkRepository:
    def __init__(self, value: WorkBundle | None = None) -> None:
        self.value = value
        self.bundles: list[WorkBundle] = []
        self.specialists: list[Actor] = []
        self.found_specialist: Actor | None = None
        self.applied = object()
        self.pending_type: str | None = None
        self.pending_actor: Actor | None = None
        self.commits = 0

    async def list_for_actor(self, user: Actor) -> list[WorkBundle]:
        assert isinstance(user.role, UserRole)
        return self.bundles

    async def page_for_actor(
        self,
        user: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
        unit_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> tuple[list[WorkBundle], str | None]:
        assert isinstance(user.role, UserRole)
        del limit, cursor, unit_id, request_id
        return self.bundles, None

    async def get(self, work_id: UUID, user: Actor | None = None) -> WorkBundle | None:
        del user
        if self.value is not None and self.value.record.id == work_id:
            return self.value
        return None

    async def find_specialist(self, user_id: UUID) -> Actor | None:
        del user_id
        return self.found_specialist

    async def list_active_specialists(self, delivery_team: str) -> list[Actor]:
        assert delivery_team
        return self.specialists

    async def prepare_claim(self, work: WorkRecord, user: Actor) -> UUID:
        self.pending_type = "claim"
        self.pending_actor = user
        assert self.value is not None and self.value.record.id == work.id
        self.value = WorkBundle(
            replace(
                self.value.record,
                task_status=WorkflowTaskStatus.CLAIM_PENDING,
                assignee_id=user.id,
            ),
            self.value.view.model_copy(
                update={"status": "CLAIM_PENDING", "assignee_id": user.id}
            ),
        )
        return uuid4()

    async def prepare_completion(
        self,
        work: WorkRecord,
        user: Actor,
        payload: CompletionPayload,
    ) -> UUID:
        del work, user, payload
        self.pending_type = "complete"
        return uuid4()

    async def commit_intent(self) -> None:
        self.commits += 1

    def expire_state(self) -> None:
        return None

    async def request_detail(self, request_id: UUID) -> object:
        del request_id
        return self.applied


class FakeCommandDispatcher:
    def __init__(self, repository: FakeWorkRepository) -> None:
        self.repository = repository
        self.error: Exception | None = None
        self.processed = True

    async def dispatch(self, outbox_id: UUID) -> bool:
        del outbox_id
        if self.error:
            raise self.error
        if self.processed and self.repository.pending_type == "claim":
            value = self.repository.value
            assert value is not None and self.repository.pending_actor is not None
            self.repository.value = WorkBundle(
                replace(value.record, task_status=WorkflowTaskStatus.CLAIMED),
                value.view.model_copy(update={"status": "CLAIMED"}),
            )
        return self.processed


@pytest.mark.asyncio
async def test_list_filters_visibility_and_adds_actions_only_when_claimed() -> None:
    triage = actor(UserRole.INTAKE_TRIAGE)
    open_item = bundle(triage)
    claimed = bundle(triage, assignee_id=triage.id)
    other_claim = bundle(triage, assignee_id=uuid4())
    completed = bundle(triage, completed=True)
    wrong_stage = bundle(triage, status=RequestStatus.COORDINATION_REVIEW)
    repository = FakeWorkRepository()
    repository.bundles = [open_item, claimed, other_claim, completed, wrong_stage]
    service = WorkService(repository, FakeCommandDispatcher(repository))
    items, cursor = await service.list_page(triage)
    assert [item.id for item in items] == [open_item.record.id, claimed.record.id]
    assert cursor is None
    assert items[0].available_actions == []
    assert "progress" in items[1].available_actions


@pytest.mark.asyncio
async def test_eligible_specialists_conceals_invalid_contexts_and_maps_success() -> (
    None
):
    lead = actor(UserRole.DELIVERY_TEAM_LEAD, scope="DELIVERY_TEAM_A")
    valid = bundle(
        lead,
        status=RequestStatus.DELIVERY_PLANNING,
        team="DELIVERY_TEAM_A",
    )
    repository = FakeWorkRepository()
    service = WorkService(repository, FakeCommandDispatcher(repository))
    with pytest.raises(ObjectNotFound):
        await service.eligible_specialists(lead, uuid4())
    repository.value = valid
    with pytest.raises(ObjectNotFound):
        await service.eligible_specialists(
            actor(UserRole.INTAKE_TRIAGE), valid.record.id
        )
    repository.value = bundle(
        lead,
        status=RequestStatus.DELIVERY_PLANNING,
        team="DELIVERY_TEAM_A",
        assignee_id=uuid4(),
    )
    with pytest.raises(ObjectNotFound):
        await service.eligible_specialists(lead, repository.value.record.id)
    repository.value = bundle(lead, status=RequestStatus.LEAD_REVIEW)
    with pytest.raises(ObjectNotFound):
        await service.eligible_specialists(lead, repository.value.record.id)
    repository.value = bundle(lead, status=RequestStatus.DELIVERY_PLANNING)
    with pytest.raises(ObjectNotFound):
        await service.eligible_specialists(lead, repository.value.record.id)

    repository.value = valid
    specialist = actor(UserRole.DELIVERY_SPECIALIST, scope="DELIVERY_TEAM_A")
    repository.specialists = [specialist]
    result = await service.eligible_specialists(lead, valid.record.id)
    assert [(item.id, item.display_name) for item in result] == [
        (specialist.id, specialist.display_name)
    ]


@pytest.mark.asyncio
async def test_claim_covers_idempotency_conflicts_outages_and_success() -> None:
    triage = actor(UserRole.INTAKE_TRIAGE)
    repository = FakeWorkRepository()
    dispatcher = FakeCommandDispatcher(repository)
    service = WorkService(repository, dispatcher)
    with pytest.raises(ObjectNotFound):
        await service.claim(triage, uuid4())

    repository.value = bundle(triage, assignee_id=uuid4())
    with pytest.raises(ObjectNotFound):
        await service.claim(triage, repository.value.record.id)
    repository.value = bundle(triage, assignee_id=triage.id)
    returned = await service.claim(triage, repository.value.record.id)
    assert "progress" in returned.available_actions
    repository.value = bundle(triage, engine_key=None)
    with pytest.raises(InvalidAction):
        await service.claim(triage, repository.value.record.id)

    repository.value = bundle(triage)
    for error, expected in [
        (WorkflowConflict("claim", 409), AlreadyClaimed),
        (WorkflowEngineUnavailable("offline"), WorkflowUnavailable),
        (WorkflowError("invalid"), InvalidAction),
    ]:
        dispatcher.error = error
        with pytest.raises(expected):
            await service.claim(triage, repository.value.record.id)
        repository.value = bundle(triage)
    dispatcher.error = None
    dispatcher.processed = False
    with pytest.raises(WorkflowUnavailable):
        await service.claim(triage, repository.value.record.id)
    repository.value = bundle(triage)
    dispatcher.processed = True
    claimed = await service.claim(triage, repository.value.record.id)
    assert "progress" in claimed.available_actions
    assert repository.commits > 0

    repository.value = bundle(
        triage,
        assignee_id=triage.id,
        task_status=WorkflowTaskStatus.CLAIM_PENDING,
    )
    with pytest.raises(WorkflowActionPending):
        await service.claim(triage, repository.value.record.id)


@pytest.mark.asyncio
async def test_claim_defensively_rejects_a_preassigned_visible_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    triage = actor(UserRole.INTAKE_TRIAGE)
    value = bundle(triage, assignee_id=uuid4())
    repository = FakeWorkRepository(value)
    service = WorkService(repository, FakeCommandDispatcher(repository))
    monkeypatch.setattr(WorkService, "_visible", staticmethod(lambda *_args: True))
    with pytest.raises(ObjectNotFound):
        await service.claim(triage, value.record.id)


@pytest.mark.asyncio
async def test_analyst_cannot_claim_an_open_task_even_if_it_is_projected() -> None:
    specialist = actor(UserRole.DELIVERY_SPECIALIST, scope="OSG Team")
    value = bundle(
        specialist,
        status=RequestStatus.IN_PROGRESS,
        specialist_id=specialist.id,
        team="OSG Team",
    )
    repository = FakeWorkRepository(value)
    repository.bundles = [value]
    service = WorkService(repository, FakeCommandDispatcher(repository))

    assert await service.list_page(specialist) == ([], None)
    with pytest.raises(ObjectNotFound):
        await service.claim(specialist, value.record.id)
