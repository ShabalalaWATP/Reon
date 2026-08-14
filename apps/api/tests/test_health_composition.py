"""Focused persistence-readiness composition coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

import istari_service.health_composition as health_composition


class HealthSessionDouble:
    async def execute(self, _statement: object) -> None:
        return None

    async def rollback(self) -> None:  # pragma: no cover - success-path double
        raise AssertionError("The healthy session must not be rolled back.")


@pytest.mark.asyncio
async def test_persistence_readiness_checks_required_worker_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    async def configuration_ready(_session: object) -> bool:
        return True

    class MaintenanceRepositoryDouble:
        def __init__(self, session: object) -> None:
            observed["session"] = session

        async def heartbeat_is_fresh(
            self, *, now: datetime, maximum_age_seconds: float
        ) -> bool:
            observed["now"] = now
            observed["maximum_age_seconds"] = maximum_age_seconds
            return True

    monkeypatch.setattr(
        health_composition,
        "configuration_runtime_is_ready",
        configuration_ready,
    )
    monkeypatch.setattr(
        health_composition,
        "SqlAlchemyMaintenanceLeaseRepository",
        MaintenanceRepositoryDouble,
    )
    session = HealthSessionDouble()
    now = datetime.now(UTC)

    result = await health_composition.check_persistence_readiness(
        cast(Any, session),
        worker_health_required=True,
        worker_heartbeat_stale_seconds=12.5,
        now=now,
    )

    assert result.database == "ok"
    assert result.configuration == "ok"
    assert result.worker_fresh is True
    assert observed == {
        "session": session,
        "now": now,
        "maximum_age_seconds": 12.5,
    }
