"""Fenced PostgreSQL leases and durable worker heartbeat state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.maintenance_models import MaintenanceJobState

HEARTBEAT_JOB = "worker-heartbeat"


@dataclass(frozen=True, slots=True)
class MaintenanceLease:
    name: str
    owner: str
    generation: int
    expires_at: datetime


class SqlAlchemyMaintenanceLeaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(
        self,
        name: str,
        owner: str,
        *,
        now: datetime,
        lease_seconds: float,
    ) -> MaintenanceLease | None:
        state = await self._locked_state(name)
        expires_at = _aware(state.lease_expires_at)
        if (
            state.lease_owner is not None
            and expires_at is not None
            and expires_at > now
        ):
            return None
        state.lease_owner = owner
        state.lease_generation += 1
        state.lease_expires_at = now + timedelta(seconds=lease_seconds)
        state.last_started_at = now
        state.last_error_code = None
        await self.session.flush()
        return MaintenanceLease(
            name=name,
            owner=owner,
            generation=state.lease_generation,
            expires_at=state.lease_expires_at,
        )

    async def succeed(self, lease: MaintenanceLease, *, now: datetime) -> bool:
        state = await self._current_lease(lease)
        if state is None:
            return False
        state.lease_owner = None
        state.lease_expires_at = None
        state.last_success_at = now
        state.last_error_code = None
        return True

    async def fail(
        self,
        lease: MaintenanceLease,
        *,
        now: datetime,
        error_code: str,
    ) -> bool:
        state = await self._current_lease(lease)
        if state is None:
            return False
        state.lease_owner = None
        state.lease_expires_at = None
        state.last_failure_at = now
        state.last_error_code = error_code[:80]
        return True

    async def renew(
        self,
        lease: MaintenanceLease,
        *,
        now: datetime,
        lease_seconds: float,
    ) -> bool:
        state = await self._current_lease(lease)
        if state is None:
            return False
        state.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return True

    async def heartbeat(
        self,
        owner: str,
        *,
        now: datetime,
        healthy: bool,
        error_code: str | None = None,
    ) -> None:
        state = await self._locked_state(HEARTBEAT_JOB)
        state.lease_owner = owner
        if healthy:
            state.last_success_at = now
            state.last_error_code = None
        else:
            state.last_failure_at = now
            state.last_error_code = (error_code or "WORKER_ITERATION_FAILED")[:80]

    async def heartbeat_is_fresh(
        self,
        *,
        now: datetime,
        maximum_age_seconds: float,
    ) -> bool:
        last_success = await self.session.scalar(
            select(MaintenanceJobState.last_success_at).where(
                MaintenanceJobState.name == HEARTBEAT_JOB
            )
        )
        observed = _aware(last_success)
        return observed is not None and observed >= now - timedelta(
            seconds=maximum_age_seconds
        )

    async def _locked_state(self, name: str) -> MaintenanceJobState:
        state = await self.session.scalar(
            select(MaintenanceJobState)
            .where(MaintenanceJobState.name == name)
            .with_for_update()
        )
        if state is None:
            state = MaintenanceJobState(name=name)
            self.session.add(state)
            await self.session.flush()
        return state

    async def _current_lease(
        self, lease: MaintenanceLease
    ) -> MaintenanceJobState | None:
        state: MaintenanceJobState | None = await self.session.scalar(
            select(MaintenanceJobState)
            .where(
                MaintenanceJobState.name == lease.name,
                MaintenanceJobState.lease_owner == lease.owner,
                MaintenanceJobState.lease_generation == lease.generation,
            )
            .with_for_update()
        )
        return state


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
