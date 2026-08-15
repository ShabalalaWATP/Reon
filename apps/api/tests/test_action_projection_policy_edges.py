"""Pure role and request-status action projection policy coverage."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from mist_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ActionSourceType,
)
from mist_service.domain import Actor
from mist_service.models import RequestStatus, ServiceRequest, UserRole
from mist_service.request_action_projection import (
    ActionAudience,
    _action_link,
    _action_type,
    _section,
    _source_type,
    action_audiences,
    as_utc,
    waiting_analyst,
)
from mist_service.services.action_service import _current_owner


def _request(status: RequestStatus, *, assigned: UUID | None = None) -> ServiceRequest:
    return ServiceRequest(
        id=uuid4(),
        requester_id=uuid4(),
        reference="SR-POLICY",
        title="Synthetic policy case",
        status=status,
        current_owner="Synthetic owner",
        required_by=datetime.now(UTC).date() + timedelta(days=10),
        assigned_specialist_id=assigned,
        awaiting_team_staffing=False,
    )


def test_action_owner_falls_back_if_a_unit_name_is_unavailable() -> None:
    actor = Actor(
        id=uuid4(),
        username="fallback",
        display_name="Fallback User",
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="Fallback scope",
    )
    action = ActionProjection(
        recipient_user_id=None,
        organisation_unit_id=uuid4(),
        current_owner="Stored owner",
    )
    assert _current_owner(action, actor, {}) == "Stored owner"


@pytest.mark.parametrize(
    ("status", "role", "path"),
    [
        (RequestStatus.TRIAGE_REVIEW, UserRole.INTAKE_TRIAGE, "/triage"),
        (
            RequestStatus.COORDINATION_REVIEW,
            UserRole.SERVICE_COORDINATION,
            "/coordination",
        ),
        (
            RequestStatus.ALLOCATION_REVIEW,
            UserRole.OPERATIONS_ALLOCATION,
            "/allocation",
        ),
        (
            RequestStatus.DELIVERY_PLANNING,
            UserRole.DELIVERY_TEAM_LEAD,
            "/delivery/team",
        ),
        (
            RequestStatus.IN_PROGRESS,
            UserRole.DELIVERY_SPECIALIST,
            "/delivery/my-work",
        ),
        (
            RequestStatus.QUALITY_REVIEW,
            UserRole.QUALITY_RELEASE,
            "/quality-release",
        ),
    ],
)
def test_staff_action_links_target_the_role_queue(
    status: RequestStatus, role: UserRole, path: str
) -> None:
    request = _request(status)
    assert (
        _action_link(
            request,
            ActionAudience(recipient_user_id=uuid4(), recipient_role=role),
        )
        == f"{path}?requestId={request.id}"
    )


def test_customer_action_links_target_the_customer_request() -> None:
    request = _request(RequestStatus.INFORMATION_REQUIRED)
    assert (
        _action_link(
            request,
            ActionAudience(
                recipient_user_id=request.requester_id,
                recipient_role=UserRole.REQUESTER,
            ),
        )
        == f"/requests/{request.id}"
    )


@pytest.mark.parametrize(
    ("status", "expected_path"),
    [
        (RequestStatus.TRIAGE_REVIEW, "/triage"),
        (RequestStatus.QUALITY_REVIEW, "/quality-release"),
        (RequestStatus.IN_PROGRESS, "/delivery/my-work"),
    ],
)
def test_action_links_fail_safe_to_the_status_queue_for_legacy_audiences(
    status: RequestStatus, expected_path: str
) -> None:
    request = _request(status)
    assert _action_link(request, ActionAudience()) == (
        f"{expected_path}?requestId={request.id}"
    )


def test_action_links_fall_back_to_the_request_for_unknown_legacy_audiences() -> None:
    request = _request(RequestStatus.COMPLETED)
    assert _action_link(request, ActionAudience()) == f"/requests/{request.id}"


@pytest.mark.asyncio
async def test_request_action_policy_status_branches(api_harness: ApiHarness) -> None:
    specialist_id = await api_harness.user_id("admin11")
    async with api_harness.sessions() as session:
        customer = _request(RequestStatus.INFORMATION_REQUIRED)
        assert (await action_audiences(session, customer))[0].recipient_user_id
        assigned = _request(RequestStatus.IN_PROGRESS, assigned=specialist_id)
        assert await action_audiences(session, assigned) == []
        assert (
            await action_audiences(session, _request(RequestStatus.IN_PROGRESS)) == []
        )
        quality = await action_audiences(
            session, _request(RequestStatus.QUALITY_REVIEW)
        )
        assert quality[0].candidate_role is UserRole.QUALITY_RELEASE
        assert (
            await action_audiences(session, _request(RequestStatus.ROUTING_PENDING))
            == []
        )
        corrupt = _request(RequestStatus.ROUTING_PENDING)
        corrupt.status = cast(Any, "UNKNOWN")
        assert await action_audiences(session, corrupt) == []

    fake_session = cast(AsyncSession, AsyncMock())
    fake_session.scalar = AsyncMock(side_effect=[None, uuid4()])  # type: ignore[method-assign]
    statuses = {
        RequestStatus.INFORMATION_REQUIRED: "PROVIDE_INFORMATION",
        RequestStatus.CUSTOMER_INFORMATION_REQUIRED: "PROVIDE_CLARIFICATION",
        RequestStatus.IN_PROGRESS: "DEVELOP_PRODUCT",
        RequestStatus.QUALITY_REVIEW: "QC_REVIEW",
        RequestStatus.READY_FOR_RELEASE: "DISSEMINATE_PRODUCT",
        RequestStatus.CLOSED_NOT_PROGRESSED: "RECENTLY_COMPLETED",
        RequestStatus.COMPLETED: "FEEDBACK_DUE",
    }
    for status, expected in statuses.items():
        assert await _action_type(fake_session, _request(status)) == expected
    assert (
        await _action_type(fake_session, _request(RequestStatus.COMPLETED))
        == "RECENTLY_COMPLETED"
    )

    now = datetime.now(UTC)
    assert (
        _section(_request(RequestStatus.COMPLETED), now)
        is ActionSection.NEEDS_MY_ACTION
    )
    assert (
        _section(_request(RequestStatus.COMPLETED), now, "RECENTLY_COMPLETED")
        is ActionSection.RECENTLY_COMPLETED
    )
    assert (
        _section(_request(RequestStatus.CANCELLED), now)
        is ActionSection.RECENTLY_COMPLETED
    )
    assert _section(_request(RequestStatus.ON_HOLD), now) is ActionSection.WAITING
    due = _request(RequestStatus.IN_PROGRESS)
    due.required_by = now.date()
    assert _section(due, now) is ActionSection.DUE_SOON
    assert (
        _section(_request(RequestStatus.IN_PROGRESS), now)
        is ActionSection.NEEDS_MY_ACTION
    )
    assert (
        _source_type(RequestStatus.CUSTOMER_INFORMATION_REQUIRED)
        is ActionSourceType.CLARIFICATION
    )
    assert _source_type(RequestStatus.COMPLETED) is ActionSourceType.FEEDBACK
    assert _source_type(RequestStatus.IN_PROGRESS) is ActionSourceType.WORKFLOW_TASK
    assert (
        waiting_analyst(_request(RequestStatus.IN_PROGRESS, assigned=specialist_id))
        is None
    )
    assert as_utc(now.replace(tzinfo=None)).tzinfo is UTC
