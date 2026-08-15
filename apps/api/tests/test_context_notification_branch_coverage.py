"""Context dependencies and notification audience branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Request

import mist_service.dependencies as dependencies
import mist_service.mutation_dependencies as mutation_dependencies
import mist_service.request_notification_projection as notifications
from conftest import ApiHarness
from mist_service.action_notification_models import NotificationAccessKind
from mist_service.config import Environment, Settings
from mist_service.domain import Actor, SessionRecord
from mist_service.errors import ObjectNotFound, SessionRequired
from mist_service.models import RequestStatus, ServiceRequest, UserRole
from mist_service.request_action_projection import ActionAudience


def _actor(role: UserRole) -> Actor:
    return Actor(uuid4(), "actor", "Synthetic Actor", role, "Synthetic scope")


def _session(actor: Actor, *, elevated_until=None) -> SessionRecord:
    return SessionRecord(
        uuid4(),
        actor,
        "synthetic-csrf-hash",
        datetime.now(UTC) + timedelta(hours=1),
        elevated_until=elevated_until,
    )


def _request() -> Request:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    return Request({"type": "http", "app": app, "headers": []})


async def test_mutation_context_and_staff_dependencies_reject_stale_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _actor(UserRole.INTAKE_TRIAGE)
    record = _session(actor)
    lock = AsyncMock(return_value=False)
    monkeypatch.setattr(mutation_dependencies, "require_csrf", lambda *_args: None)
    monkeypatch.setattr(
        mutation_dependencies,
        "SqlAlchemyAuthRepository",
        lambda _database: SimpleNamespace(lock_mutation_context=lock),
    )
    with pytest.raises(SessionRequired):
        await dependencies.mutation_session(_request(), record, SimpleNamespace())
    with pytest.raises(ObjectNotFound):
        dependencies.staff_mutation_actor(_session(_actor(UserRole.REQUESTER)))


async def test_naive_future_step_up_is_normalised() -> None:
    actor = _actor(UserRole.PLATFORM_ADMIN)
    naive_future = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
    assert (
        await dependencies.elevated_mutation_actor(
            _request(), _session(actor, elevated_until=naive_future)
        )
        == actor
    )


async def test_route_scope_and_invalid_direct_notification_audiences(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = ServiceRequest(
        id=uuid4(),
        requester_id=uuid4(),
        reference="SR-NOTIFICATION-BRANCH",
        title="Synthetic notification branch",
        status=RequestStatus.TRIAGE_REVIEW,
        current_owner="CRIOC",
    )
    route_user_id = uuid4()
    scope_user_id = uuid4()

    async def audiences(_session, _request):
        return [
            ActionAudience(
                candidate_role=UserRole.INTAKE_TRIAGE,
                organisation_unit_id=uuid4(),
            ),
            ActionAudience(
                candidate_role=UserRole.SERVICE_COORDINATION,
                required_scope="Shared coordination",
            ),
            ActionAudience(),
        ]

    async def route_rules(_session, _unit_id, role):
        return [
            notifications.RecipientRule(
                route_user_id, NotificationAccessKind.ROUTE_MEMBER, role
            )
        ]

    async def scope_rules(_session, _scope, role):
        return [
            notifications.RecipientRule(
                scope_user_id, NotificationAccessKind.ROLE_SCOPE, role
            )
        ]

    monkeypatch.setattr(notifications, "action_audiences", audiences)
    monkeypatch.setattr(notifications, "_route_rules", route_rules)
    monkeypatch.setattr(notifications, "_scope_rules", scope_rules)
    async with api_harness.sessions() as session:
        rules = await notifications.recipient_rules_for(session, "TASK_READY", request)
        assert {rule.user_id for rule in rules} == {route_user_id, scope_user_id}

    with pytest.raises(ValueError, match="recipient role"):
        notifications._direct_rule(request, uuid4(), None)


async def test_quality_scope_resolves_exact_qc_team(api_harness: ApiHarness) -> None:
    async with api_harness.sessions() as session:
        rules = await notifications._scope_rules(
            session,
            "Combined QC Team",
            UserRole.QUALITY_RELEASE,
        )
    assert len(rules) == 2
    assert all(
        rule.access_kind is NotificationAccessKind.ROUTE_MEMBER for rule in rules
    )


async def test_non_quality_scope_resolves_active_role_scope_users() -> None:
    user_id = uuid4()
    session = SimpleNamespace(scalars=AsyncMock(return_value=[user_id]))

    rules = await notifications._scope_rules(
        session,
        "Shared coordination",
        UserRole.SERVICE_COORDINATION,
    )

    assert len(rules) == 1
    assert rules[0].user_id == user_id
    assert rules[0].access_kind is NotificationAccessKind.ROLE_SCOPE
