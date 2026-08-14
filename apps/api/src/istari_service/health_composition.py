"""Persistence adapter for dependency-readiness checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_readiness import configuration_runtime_is_ready
from istari_service.repositories.maintenance_leases import (
    SqlAlchemyMaintenanceLeaseRepository,
)


@dataclass(frozen=True, slots=True)
class PersistenceReadiness:
    database: Literal["ok", "unavailable"]
    configuration: Literal["ok", "unavailable"]
    worker_fresh: bool


async def check_persistence_readiness(
    session: AsyncSession,
    *,
    worker_health_required: bool,
    worker_heartbeat_stale_seconds: float,
    now: datetime,
) -> PersistenceReadiness:
    """Check database-backed dependencies without hiding rollback behaviour."""

    try:
        await session.execute(text("SELECT 1"))
        configuration_ready = await configuration_runtime_is_ready(session)
        worker_fresh = not worker_health_required or (
            await SqlAlchemyMaintenanceLeaseRepository(session).heartbeat_is_fresh(
                now=now,
                maximum_age_seconds=worker_heartbeat_stale_seconds,
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return PersistenceReadiness("unavailable", "unavailable", False)
    return PersistenceReadiness(
        "ok",
        "ok" if configuration_ready else "unavailable",
        worker_fresh,
    )
