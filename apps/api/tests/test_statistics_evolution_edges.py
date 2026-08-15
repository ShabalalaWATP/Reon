"""Bounded-query and suppression edge coverage for evolved statistics."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from mist_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound, StatisticsQueryInvalid
from mist_service.models import RequestStatus, UserRole
from mist_service.organisation_models import OrganisationKind
from mist_service.repositories import statistics_evolution as repository_module
from mist_service.repositories.statistics_evolution import (
    SqlAlchemyStatisticsEvolutionRepository,
)
from mist_service.schemas.statistics import StatisticsScope, StatisticsUnit
from mist_service.schemas.statistics_evolution import StatisticsExportCommand
from mist_service.services.statistics_evolution_service import (
    StatisticsEvolutionService,
)
from mist_service.statistics_evolution_calculations import (
    _bottleneck_rows,
    _interval_seconds,
)
from mist_service.statistics_hierarchy import (
    selected_statistics_unit,
    statistics_breadcrumb,
)
from mist_service.statistics_operational_calculations import (
    capacity_rows,
    notification_rows,
)
from mist_service.statistics_throughput import throughput_rows


def _fact() -> OperationalAnalyticsFact:
    unit_id = uuid4()
    return OperationalAnalyticsFact(
        source_key="synthetic-capacity-small",
        type=OperationalFactType.CAPACITY_AVAILABLE,
        root_unit_id=unit_id,
        command_unit_id=unit_id,
        ops_unit_id=unit_id,
        team_unit_id=unit_id,
        occurred_at=datetime.now(UTC),
        count_value=2,
        duration_seconds=None,
        measure_minutes=60,
        definition_version=1,
        projection_version=1,
    )


def test_empty_notifications_small_capacity_and_aware_interval() -> None:
    assert notification_rows(()) == []
    assert capacity_rows((_fact(),), ZoneInfo("UTC")) == []
    now = datetime.now(UTC)
    interval = SimpleNamespace(
        duration_seconds=None, started_at=now - timedelta(hours=1)
    )
    assert _interval_seconds(interval, now) == 3600


def test_terminal_intervals_are_not_active_bottlenecks() -> None:
    now = datetime.now(UTC)
    terminal = SimpleNamespace(
        status=RequestStatus.COMPLETED,
        duration_seconds=None,
        started_at=now - timedelta(hours=8),
        ended_at=None,
        request_id=uuid4(),
    )
    active = SimpleNamespace(
        status=RequestStatus.IN_PROGRESS,
        duration_seconds=None,
        started_at=now - timedelta(hours=1),
        ended_at=None,
        request_id=uuid4(),
    )
    dataset = SimpleNamespace(intervals=(terminal, active), facts=())
    rows = _bottleneck_rows(dataset, now)
    assert [row.key for row in rows] == [RequestStatus.IN_PROGRESS.value]


def test_statistics_hierarchy_selects_only_members_and_builds_a_trail() -> None:
    root_id = uuid4()
    child_id = uuid4()
    root = StatisticsUnit(
        id=root_id,
        parent_id=None,
        name="CRIOC",
        kind=OrganisationKind.ROOT,
        depth=0,
    )
    child = StatisticsUnit(
        id=child_id,
        parent_id=root_id,
        name="JOCK",
        kind=OrganisationKind.COMMAND,
        depth=1,
    )
    scope = StatisticsScope(
        id="crioc",
        unit_id=root_id,
        name="CRIOC",
        kind=OrganisationKind.ROOT,
        include_descendants=True,
        units=[root, child],
    )

    selected = selected_statistics_unit(scope, child_id)
    assert selected == child
    assert statistics_breadcrumb(scope, selected) == (root, child)
    with pytest.raises(ObjectNotFound):
        selected_statistics_unit(scope, uuid4())


def test_statistics_breadcrumb_fails_closed_for_broken_parent_links() -> None:
    root_id = uuid4()
    scope = StatisticsScope(
        id="broken",
        unit_id=root_id,
        name="Broken synthetic scope",
        kind=OrganisationKind.ROOT,
        include_descendants=True,
        units=[],
    )
    without_parent = StatisticsUnit(
        id=uuid4(),
        parent_id=None,
        name="Detached",
        kind=OrganisationKind.COMMAND,
        depth=1,
    )
    missing_parent = without_parent.model_copy(
        update={"id": uuid4(), "parent_id": uuid4()}
    )

    with pytest.raises(ObjectNotFound):
        statistics_breadcrumb(scope, without_parent)
    with pytest.raises(ObjectNotFound):
        statistics_breadcrumb(scope, missing_parent)


async def test_operational_fact_query_cap_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repository_module, "MAX_FACT_ROWS", 1)
    session = AsyncMock()
    session.scalars.return_value = (_fact(), _fact())
    repository = SqlAlchemyStatisticsEvolutionRepository(session)
    unit_id = uuid4()
    repository._base = SimpleNamespace(  # type: ignore[assignment]
        load_dataset=AsyncMock(return_value=object()),
        authorised_scope=AsyncMock(
            return_value=(
                object(),
                SimpleNamespace(id=unit_id, kind=OrganisationKind.TEAM),
            )
        ),
    )
    actor = Actor(
        id=uuid4(),
        username="synthetic-statistics-user",
        display_name="Synthetic Statistics User",
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="synthetic",
    )
    now = datetime.now(UTC)
    with pytest.raises(StatisticsQueryInvalid, match="Reduce"):
        await repository.load(
            actor,
            scope_id=str(uuid4()),
            start=now - timedelta(days=1),
            end=now,
            previous_start=now - timedelta(days=2),
            previous_end=now - timedelta(days=1),
            at=now,
        )


async def test_export_rejects_a_scope_without_a_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = AsyncMock()
    service = StatisticsEvolutionService(repository, repository)
    monkeypatch.setattr(
        service,
        "dashboard",
        AsyncMock(return_value=SimpleNamespace(scope=SimpleNamespace(unit_id=None))),
    )
    today = datetime.now(UTC).date()
    command = StatisticsExportCommand.model_validate(
        {
            "scopeId": "platform",
            "from": today.isoformat(),
            "to": today.isoformat(),
            "timeZone": "UTC",
            "format": "CSV",
        }
    )
    with pytest.raises(StatisticsQueryInvalid, match="scope is unavailable"):
        await service.request_export(_actor(), command)


def _actor() -> Actor:
    return Actor(
        id=uuid4(),
        username="synthetic-statistics-user",
        display_name="Synthetic Statistics User",
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="synthetic",
    )


def test_throughput_rows_advance_weekly_and_monthly_buckets() -> None:
    zone = ZoneInfo("Europe/London")
    weekly = throughput_rows((), date(2026, 8, 2), date(2026, 8, 18), zone, "WEEKLY")
    monthly = throughput_rows((), date(2026, 1, 20), date(2026, 3, 2), zone, "MONTHLY")
    assert [row.date for row in weekly] == [
        date(2026, 7, 27),
        date(2026, 8, 3),
        date(2026, 8, 10),
        date(2026, 8, 17),
    ]
    assert [row.date for row in monthly] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
