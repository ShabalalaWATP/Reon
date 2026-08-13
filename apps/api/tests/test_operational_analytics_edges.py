"""Operational analytics projector boundary and repair tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness
from istari_service.analytics_evolution_models import OperationalFactType
from istari_service.board_models import IterationStatus, TeamIteration
from istari_service.calendar_models import CalendarCapacitySnapshot
from istari_service.models import ServiceRequest
from istari_service.operational_analytics_facts import (
    OperationalFactInput,
    OperationalScope,
    append_operational_fact,
    request_operational_scope,
    unit_operational_scope,
)
from istari_service.operational_analytics_projection import (
    project_capacity_snapshot_facts,
    project_closed_iteration_facts,
    project_notification_response_fact,
    project_notification_sent_fact,
    project_product_access_fact,
    project_request_operational_event,
)
from istari_service.operational_analytics_reconciliation import (
    reconcile_operational_analytics,
)
from istari_service.organisation_models import OrganisationKind
from istari_service.product_models import ProductAccessEvent
from istari_service.product_types import AccessKind, AccessOutcome
from istari_service.request_event_models import RequestEvent


class _ScalarResult:
    def __init__(self, value: UUID | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> UUID | None:
        return self.value


class _AppendSession:
    def __init__(self, dialect: str, value: UUID | None = None) -> None:
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))
        self.value = value
        self.statement: Any = None

    def get_bind(self) -> Any:
        return self.bind

    async def execute(self, statement: Any) -> _ScalarResult:
        self.statement = statement
        return _ScalarResult(self.value)


class _ScopeSession:
    def __init__(self, units: dict[UUID, Any]) -> None:
        self.units = units

    async def get(self, _model: type[Any], key: UUID) -> Any:
        return self.units.get(key)


class _Rows:
    def __init__(self, items: list[Any]) -> None:
        self.items = items

    def all(self) -> list[Any]:
        return self.items

    def __iter__(self) -> Any:
        return iter(self.items)


class _ReplaySession:
    async def execute(self, _statement: Any) -> _Rows:
        return _Rows([(object(), object()), (object(), object())])

    async def scalars(self, _statement: Any) -> _Rows:
        return _Rows([])


class _ProductSession:
    def __init__(self, released_at: datetime) -> None:
        self.released_at = released_at

    async def scalar(self, _statement: Any) -> datetime:
        return self.released_at


def _fact() -> OperationalFactInput:
    return OperationalFactInput(
        source_key="request-event:" + "a" * 64,
        type=OperationalFactType.DISSEMINATION_RELEASED,
        scope=OperationalScope(root_unit_id=uuid4()),
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    )


async def test_append_uses_postgresql_conflict_insert_and_rejects_other_dialects() -> (
    None
):
    postgres = _AppendSession("postgresql", uuid4())
    assert await append_operational_fact(cast(AsyncSession, postgres), _fact())
    assert postgres.statement is not None

    unsupported = _AppendSession("mysql")
    with pytest.raises(
        RuntimeError, match="operational analytics requires PostgreSQL or SQLite"
    ):
        await append_operational_fact(cast(AsyncSession, unsupported), _fact())


async def test_scope_resolution_fails_closed_for_missing_or_cyclic_routes(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session:
        assert await request_operational_scope(session, uuid4()) is None
        assert await unit_operational_scope(session, uuid4()) is None

    cycle_id = uuid4()
    cycle = SimpleNamespace(
        id=cycle_id,
        kind=OrganisationKind.ROOT,
        parent_id=cycle_id,
    )
    cycle_session = _ScopeSession({cycle_id: cycle})
    resolved = await unit_operational_scope(cast(AsyncSession, cycle_session), cycle_id)
    assert resolved is None


async def test_projectors_skip_unrecognised_or_unscoped_sources(
    api_harness: ApiHarness,
) -> None:
    now = datetime.now(UTC)
    request = cast(
        ServiceRequest,
        SimpleNamespace(id=uuid4(), created_at=now - timedelta(minutes=5)),
    )
    unknown = cast(RequestEvent, SimpleNamespace(type="REQUEST_CREATED"))
    workflow_release = cast(RequestEvent, SimpleNamespace(type="WORKFLOW_RELEASE"))
    release = cast(RequestEvent, SimpleNamespace(type="PRODUCT_DISSEMINATED"))
    denied = cast(
        ProductAccessEvent,
        SimpleNamespace(outcome=AccessOutcome.DENIED, request_id=request.id),
    )
    unscoped_access = cast(
        ProductAccessEvent,
        SimpleNamespace(
            outcome=AccessOutcome.ALLOWED,
            request_id=request.id,
            kind=AccessKind.DOWNLOAD,
        ),
    )
    notification = SimpleNamespace(request_id=None)
    planned = cast(TeamIteration, SimpleNamespace(status=IterationStatus.PLANNED))
    closed = cast(
        TeamIteration,
        SimpleNamespace(status=IterationStatus.CLOSED, team_id=uuid4()),
    )
    snapshot = cast(CalendarCapacitySnapshot, SimpleNamespace(team_id=uuid4()))

    async with api_harness.sessions() as session:
        assert await project_request_operational_event(session, unknown, request) == 0
        assert (
            await project_request_operational_event(session, workflow_release, request)
            == 0
        )
        assert await project_request_operational_event(session, release, request) == 0
        assert await project_product_access_fact(session, denied) == 0
        assert await project_product_access_fact(session, unscoped_access) == 0
        assert await project_notification_sent_fact(session, notification) == 0
        assert await project_notification_response_fact(session, notification, now) == 0
        assert await project_closed_iteration_facts(session, planned) == 0
        assert await project_closed_iteration_facts(session, closed) == 0
        assert await project_capacity_snapshot_facts(session, snapshot) == 0


async def test_product_access_projects_release_to_access_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from istari_service import operational_analytics_projection as projection

    released_at = datetime(2026, 1, 1, 9, tzinfo=UTC)
    accessed_at = released_at + timedelta(minutes=8)
    request_id = uuid4()
    captured: list[OperationalFactInput] = []

    async def scope(_session: AsyncSession, _request_id: UUID) -> OperationalScope:
        return OperationalScope(root_unit_id=uuid4())

    async def append(_session: AsyncSession, fact: OperationalFactInput) -> bool:
        captured.append(fact)
        return True

    monkeypatch.setattr(projection, "request_operational_scope", scope)
    monkeypatch.setattr(projection, "append_operational_fact", append)
    event = cast(
        ProductAccessEvent,
        SimpleNamespace(
            id=uuid4(),
            outcome=AccessOutcome.ALLOWED,
            request_id=request_id,
            package_id=uuid4(),
            kind=AccessKind.REDIRECT,
            created_at=accessed_at,
        ),
    )

    inserted = await project_product_access_fact(
        cast(AsyncSession, _ProductSession(released_at)), event
    )

    assert inserted == 1
    assert captured[0].type is OperationalFactType.DISSEMINATION_LINK_OPENED
    assert captured[0].duration_seconds == 480


async def test_replay_rejects_windows_above_the_source_limit() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="Reduce the operational analytics replay"):
        await reconcile_operational_analytics(
            cast(AsyncSession, _ReplaySession()),
            start=now - timedelta(minutes=1),
            end=now + timedelta(minutes=1),
            source_limit=1,
        )
