"""Bounded-query and suppression edge coverage for evolved statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from istari_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from istari_service.domain import Actor
from istari_service.errors import StatisticsQueryInvalid
from istari_service.models import UserRole
from istari_service.organisation_models import OrganisationKind
from istari_service.repositories import statistics_evolution as repository_module
from istari_service.repositories.statistics_evolution import (
    SqlAlchemyStatisticsEvolutionRepository,
)
from istari_service.schemas.statistics_evolution import StatisticsExportCommand
from istari_service.services.statistics_evolution_service import (
    StatisticsEvolutionService,
)
from istari_service.statistics_evolution_calculations import _interval_seconds
from istari_service.statistics_operational_calculations import (
    capacity_rows,
    notification_rows,
)


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
    service = StatisticsEvolutionService(repository)
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
