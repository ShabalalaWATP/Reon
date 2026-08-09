"""Independent, fenced and failure-isolated maintenance worker loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.repositories.maintenance_leases import (
    MaintenanceLease,
    SqlAlchemyMaintenanceLeaseRepository,
)

LOGGER = logging.getLogger(__name__)
JobCallback = Callable[[], Coroutine[Any, Any, bool]]
LEASE_LOST = "MaintenanceLeaseLost"


class MaintenanceLeaseLostError(RuntimeError):
    """Stop a callback whose named worker lease can no longer be renewed."""


@dataclass(frozen=True, slots=True)
class MaintenanceJob:
    name: str
    callback: JobCallback


class WorkerIteration:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        jobs: tuple[MaintenanceJob, ...],
        *,
        lease_seconds: float,
        owner: str | None = None,
    ) -> None:
        self._sessions = sessions
        self._jobs = jobs
        self._lease_seconds = lease_seconds
        self.owner = owner or uuid4().hex

    async def run_once(self) -> bool:
        worked = False
        failures: list[str] = []
        for job in self._jobs:
            lease = await self._claim(job.name)
            if lease is None:
                continue
            try:
                worked = await self._run_job(job, lease) or worked
            except Exception as error:
                code = type(error).__name__[:80]
                failures.append(code)
                await self._finish(lease, error_code=code)
                LOGGER.exception("Maintenance job %s failed.", job.name)
                continue
            if not await self._finish(lease):
                failures.append(LEASE_LOST)
                LOGGER.error("Maintenance job %s lost its lease.", job.name)
        await self._heartbeat(failures)
        return worked

    async def _run_job(
        self,
        job: MaintenanceJob,
        lease: MaintenanceLease,
    ) -> bool:
        stop = asyncio.Event()
        callback: asyncio.Task[bool] = asyncio.create_task(job.callback())
        renewal = asyncio.create_task(self._keep_lease(lease, stop))
        try:
            done, _ = await asyncio.wait(
                {callback, renewal}, return_when=asyncio.FIRST_COMPLETED
            )
            if renewal in done:
                try:
                    renewed = renewal.result()
                except Exception:
                    callback.cancel()
                    await asyncio.gather(callback, return_exceptions=True)
                    raise
                if not renewed:
                    callback.cancel()
                    await asyncio.gather(callback, return_exceptions=True)
                    raise MaintenanceLeaseLostError(LEASE_LOST)
            return await callback
        finally:
            stop.set()
            if not renewal.done():
                await renewal

    async def _keep_lease(
        self,
        lease: MaintenanceLease,
        stop: asyncio.Event,
    ) -> bool:
        interval = min(max(self._lease_seconds / 3, 0.25), 2.0)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return True
            except TimeoutError:
                if not await self._renew(lease):
                    return False
        return True

    async def _claim(self, name: str) -> MaintenanceLease | None:
        async with self._sessions() as session, session.begin():
            return await SqlAlchemyMaintenanceLeaseRepository(session).claim(
                name,
                self.owner,
                now=datetime.now(UTC),
                lease_seconds=self._lease_seconds,
            )

    async def _finish(
        self,
        lease: MaintenanceLease,
        *,
        error_code: str | None = None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            repository = SqlAlchemyMaintenanceLeaseRepository(session)
            now = datetime.now(UTC)
            if error_code is None:
                return await repository.succeed(lease, now=now)
            return await repository.fail(lease, now=now, error_code=error_code)

    async def _renew(self, lease: MaintenanceLease) -> bool:
        async with self._sessions() as session, session.begin():
            repository = SqlAlchemyMaintenanceLeaseRepository(session)
            now = datetime.now(UTC)
            renewed = await repository.renew(
                lease,
                now=now,
                lease_seconds=self._lease_seconds,
            )
            if renewed:
                await repository.heartbeat(self.owner, now=now, healthy=True)
            return renewed

    async def _heartbeat(self, failures: list[str]) -> None:
        async with self._sessions() as session, session.begin():
            await SqlAlchemyMaintenanceLeaseRepository(session).heartbeat(
                self.owner,
                now=datetime.now(UTC),
                healthy=not failures,
                error_code=failures[0] if failures else None,
            )


async def run_worker(
    iteration: WorkerIteration,
    stop: asyncio.Event,
    *,
    interval_seconds: float,
) -> None:
    while not stop.is_set():
        worked = await iteration.run_once()
        if worked:
            continue
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue
