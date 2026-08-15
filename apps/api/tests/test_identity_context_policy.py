"""Conflict-of-interest policy for dual-context operational identities."""

from uuid import uuid4

import pytest

from mist_service.authorisation import RequestOperation
from mist_service.domain import Actor, RequestRecord
from mist_service.models import RequestStatus, UserRole
from mist_service.policies import (
    allowed_actions,
    decide_request_access,
    decide_work_completion,
    may_claim,
)


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (UserRole.INTAKE_TRIAGE, RequestStatus.TRIAGE_REVIEW),
        (UserRole.SERVICE_COORDINATION, RequestStatus.COORDINATION_REVIEW),
        (UserRole.OPERATIONS_ALLOCATION, RequestStatus.ALLOCATION_REVIEW),
        (UserRole.DELIVERY_TEAM_LEAD, RequestStatus.DELIVERY_PLANNING),
        (UserRole.DELIVERY_SPECIALIST, RequestStatus.IN_PROGRESS),
        (UserRole.QUALITY_RELEASE, RequestStatus.QUALITY_REVIEW),
        (UserRole.QUALITY_RELEASE, RequestStatus.READY_FOR_RELEASE),
    ],
)
def test_staff_context_cannot_process_its_own_customer_request(
    role: UserRole,
    status: RequestStatus,
) -> None:
    user_id = uuid4()
    team_id = uuid4()
    actor = Actor(
        id=user_id,
        username="dual-context@example.test",
        display_name="Dual Context User",
        role=role,
        scope="SSG Team",
        organisation_unit_ids=frozenset({team_id}),
    )
    request = RequestRecord(
        id=uuid4(),
        requester_id=user_id,
        status=status,
        assigned_delivery_team="SSG Team",
        assigned_delivery_team_id=team_id,
        assigned_specialist_id=user_id,
        participant_ids=frozenset({user_id}),
        version=1,
    )

    assert not decide_request_access(actor, RequestOperation.VIEW, request).allowed
    assert not may_claim(actor, request)
    assert allowed_actions(actor, request) == ()
    assert not decide_work_completion(actor, request, "approve", user_id).allowed


def test_same_identity_can_own_request_in_customer_context() -> None:
    user_id = uuid4()
    actor = Actor(
        id=user_id,
        username="dual-context@example.test",
        display_name="Dual Context User",
        role=UserRole.REQUESTER,
        scope="Customer",
    )
    request = RequestRecord(
        id=uuid4(),
        requester_id=user_id,
        status=RequestStatus.ROUTING_PENDING,
        assigned_delivery_team=None,
        assigned_specialist_id=None,
        version=1,
    )

    assert decide_request_access(actor, RequestOperation.VIEW, request).allowed
