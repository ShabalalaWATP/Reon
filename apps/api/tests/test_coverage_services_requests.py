"""Branch-complete request-service policy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from istari_service.domain import Actor, RequestRecord
from istari_service.errors import FeedbackUnavailable, ObjectNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestCreate,
    RequestDetail,
    RequestSummary,
    Sensitivity,
)
from istari_service.services.request_service import RequestService


def actor(
    role: UserRole, *, user_id: UUID | None = None, scope: str = "Area A"
) -> Actor:
    return Actor(
        user_id or uuid4(),
        f"{role.value.lower()}@example.test",
        "Synthetic User",
        role,
        scope,
    )


def command(*, area: str = "Area A") -> RequestCreate:
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
        requesting_business_area=area,
        intended_recipients=["Synthetic recipient"],
        sensitivity=Sensitivity.STANDARD,
        handling_instructions="Retain synthetic content only.",
    )


def record(
    requester_id: UUID,
    status: RequestStatus = RequestStatus.ROUTING_PENDING,
) -> RequestRecord:
    return RequestRecord(uuid4(), requester_id, status, None, None, 1)


class FakeRequestRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, RequestRecord] = {}
        self.reveal: bool | None = None
        self.includes_clarifications: list[bool] = []
        self.created = cast(RequestDetail, object())
        self.detail = cast(RequestDetail, object())
        self.feedback = cast(FeedbackView, object())
        self.summaries = [cast(RequestSummary, object())]
        self.created_for: Actor | None = None
        self.listed_for: UUID | None = None
        self.assigned_actor_ids: set[UUID] = set()
        self.record_locks: list[bool] = []

    async def create(self, user: Actor, request: RequestCreate) -> RequestDetail:
        self.created_for = user
        assert request.title == "Synthetic service request"
        return self.created

    async def list_for_requester(self, requester_id: UUID) -> list[RequestSummary]:
        self.listed_for = requester_id
        return self.summaries

    async def get_record_for_actor(
        self,
        request_id: UUID,
        user: Actor,
        *,
        lock: bool = False,
    ) -> RequestRecord | None:
        self.record_locks.append(lock)
        value = self.records.get(request_id)
        if value is None:
            return None
        if user.role is UserRole.REQUESTER:
            return value if value.requester_id == user.id else None
        return value if user.id in self.assigned_actor_ids else None

    async def get_detail(
        self,
        request_id: UUID,
        *,
        reveal_unreleased_deliverable: bool,
        include_clarifications: bool = False,
    ) -> RequestDetail:
        assert request_id in self.records
        self.reveal = reveal_unreleased_deliverable
        self.includes_clarifications.append(include_clarifications)
        return self.detail

    async def add_feedback(
        self,
        request_id: UUID,
        user: Actor,
        request: FeedbackCreate,
    ) -> FeedbackView:
        assert request_id in self.records
        assert user.id == self.records[request_id].requester_id
        assert request.rating == 5
        return self.feedback


@pytest.mark.asyncio
async def test_create_and_list_enforce_requester_scope() -> None:
    repository = FakeRequestRepository()
    service = RequestService(repository)
    requester = actor(UserRole.REQUESTER)
    staff = actor(UserRole.INTAKE_TRIAGE)
    with pytest.raises(ObjectNotFound):
        await service.create(staff, command())
    with pytest.raises(ObjectNotFound):
        await service.create(requester, command(area="Area B"))
    assert await service.create(requester, command()) is repository.created
    assert repository.created_for == requester

    with pytest.raises(ObjectNotFound):
        await service.list(staff)
    assert await service.list(requester) == repository.summaries
    assert repository.listed_for == requester.id


@pytest.mark.asyncio
async def test_get_conceals_missing_and_out_of_scope_records() -> None:
    repository = FakeRequestRepository()
    service = RequestService(repository)
    requester = actor(UserRole.REQUESTER)
    with pytest.raises(ObjectNotFound):
        await service.get(requester, uuid4())

    request_id = uuid4()
    repository.records[request_id] = record(uuid4())
    with pytest.raises(ObjectNotFound):
        await service.get(requester, request_id)

    repository.records[request_id] = record(requester.id)
    assert await service.get(requester, request_id) is repository.detail
    assert repository.reveal is False
    assert repository.includes_clarifications[-1] is True
    assert repository.record_locks[-1] is True

    triage = actor(UserRole.INTAKE_TRIAGE)
    repository.records[request_id] = record(
        requester.id,
        RequestStatus.TRIAGE_REVIEW,
    )
    with pytest.raises(ObjectNotFound):
        await service.get(triage, request_id)
    repository.assigned_actor_ids.add(triage.id)
    assert await service.get(triage, request_id) is repository.detail
    assert repository.includes_clarifications[-1] is False
    assert repository.reveal is True


@pytest.mark.asyncio
async def test_feedback_requires_owner_completion_and_single_submission() -> None:
    repository = FakeRequestRepository()
    service = RequestService(repository)
    requester = actor(UserRole.REQUESTER)
    command_value = FeedbackCreate(rating=5, comments="Synthetic feedback.")
    request_id = uuid4()
    with pytest.raises(ObjectNotFound):
        await service.add_feedback(requester, request_id, command_value)

    repository.records[request_id] = record(requester.id, RequestStatus.COMPLETED)
    with pytest.raises(ObjectNotFound):
        await service.add_feedback(
            actor(UserRole.QUALITY_RELEASE), request_id, command_value
        )
    wrong_requester = actor(UserRole.REQUESTER)
    with pytest.raises(ObjectNotFound):
        await service.add_feedback(wrong_requester, request_id, command_value)

    repository.records[request_id] = record(requester.id, RequestStatus.CANCELLED)
    with pytest.raises(FeedbackUnavailable):
        await service.add_feedback(requester, request_id, command_value)
    repository.records[request_id] = record(requester.id, RequestStatus.COMPLETED)
    assert (
        await service.add_feedback(requester, request_id, command_value)
        is repository.feedback
    )
