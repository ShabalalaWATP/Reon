"""Branch tests for final request-detail scope checks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import true

from istari_service.domain import Actor
from istari_service.models import RequestStatus, UserRole
from istari_service.repositories import request_scope
from istari_service.repositories.requests import SqlAlchemyRequestRepository


def _actor(role: UserRole, *, scope: str = "OSG Team") -> Actor:
    return Actor(uuid4(), "user@example.test", "Synthetic User", role, scope)


def _user(actor: Actor, **updates: object) -> SimpleNamespace:
    values = {
        "id": actor.id,
        "is_active": True,
        "role": actor.role,
        "scope": actor.scope,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _request(actor: Actor) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        assigned_delivery_team="OSG Team",
        assigned_specialist_id=actor.id,
        version=4,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "inactive", "role", "scope"])
async def test_locked_lookup_rejects_changed_or_missing_current_user(
    invalid: str | None,
) -> None:
    actor = _actor(UserRole.DELIVERY_SPECIALIST)
    current = None
    if invalid is not None:
        updates: dict[str, object] = {}
        if invalid == "inactive":
            updates["is_active"] = False
        elif invalid == "role":
            updates["role"] = UserRole.DELIVERY_TEAM_LEAD
        else:
            updates["scope"] = "Another Team"
        current = _user(actor, **updates)
    session = SimpleNamespace(scalar=AsyncMock(return_value=current))
    repository = SqlAlchemyRequestRepository(session, process_id="service-request-v1")
    assert await repository.get_record_for_actor(uuid4(), actor, lock=True) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST],
)
async def test_waiting_clarification_is_visible_to_exact_team_roles_without_lock(
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole,
) -> None:
    actor = _actor(role)
    request = _request(actor)
    monkeypatch.setattr(
        request_scope,
        "route_membership_condition",
        lambda _actor: None,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=request),
        scalars=AsyncMock(return_value=[]),
    )
    repository = SqlAlchemyRequestRepository(session, process_id="service-request-v1")
    record = await repository.get_record_for_actor(request.id, actor)
    assert record is not None and record.id == request.id


@pytest.mark.asyncio
async def test_locked_waiting_lookup_rechecks_route_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _actor(UserRole.DELIVERY_SPECIALIST)
    request = _request(actor)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[_user(actor), None, request]),
        scalars=AsyncMock(return_value=[]),
    )
    membership = AsyncMock(return_value=True)
    monkeypatch.setattr(request_scope, "has_route_membership", membership)
    monkeypatch.setattr(
        request_scope,
        "route_membership_condition",
        lambda _actor: true(),
    )
    repository = SqlAlchemyRequestRepository(session, process_id="service-request-v1")
    record = await repository.get_record_for_actor(request.id, actor, lock=True)
    assert record is not None
    membership.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        UserRole.DELIVERY_TEAM_LEAD,
        UserRole.DELIVERY_SPECIALIST,
        UserRole.INTAKE_TRIAGE,
    ],
)
async def test_missing_waiting_record_falls_through_role_scoped_work_query(
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole,
) -> None:
    actor = _actor(role)
    monkeypatch.setattr(
        request_scope,
        "route_membership_condition",
        lambda _actor: None,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    repository = SqlAlchemyRequestRepository(session, process_id="service-request-v1")
    assert await repository.get_record_for_actor(uuid4(), actor) is None
