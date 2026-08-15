"""Lease fencing, renewal, failure isolation and worker-loop contention."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.maintenance_models import MaintenanceJobState
from mist_service.repositories.maintenance_leases import (
    HEARTBEAT_JOB,
    MaintenanceLease,
    SqlAlchemyMaintenanceLeaseRepository,
)
from mist_service.worker_runtime import (
    LEASE_LOST,
    MaintenanceJob,
    MaintenanceLeaseLostError,
    WorkerIteration,
    run_worker,
)


@pytest.fixture
async def worker_database(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    path = tmp_path / "worker.db"
    settings = Settings(
        environment=Environment.TEST,
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    sessions = create_session_factory(engine)
    async with sessions() as session, session.begin():
        session.add_all(
            MaintenanceJobState(name=name)
            for name in (HEARTBEAT_JOB, "contention", "renewal", "failure", "idle")
        )
    yield engine, sessions
    await engine.dispose()


async def test_lease_takeover_fences_stale_completion(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        first = await SqlAlchemyMaintenanceLeaseRepository(session).claim(
            "contention", "worker-a", now=now, lease_seconds=5
        )
    assert first is not None and first.generation == 1

    async with sessions() as session, session.begin():
        repository = SqlAlchemyMaintenanceLeaseRepository(session)
        assert (
            await repository.claim(
                "contention",
                "worker-b",
                now=now + timedelta(seconds=1),
                lease_seconds=5,
            )
            is None
        )
        second = await repository.claim(
            "contention", "worker-b", now=now + timedelta(seconds=6), lease_seconds=5
        )
    assert second is not None and second.generation == 2

    async with sessions() as session, session.begin():
        repository = SqlAlchemyMaintenanceLeaseRepository(session)
        assert not await repository.succeed(first, now=now + timedelta(seconds=7))
        assert await repository.renew(
            second,
            now=now + timedelta(seconds=7),
            lease_seconds=5,
        )
        assert await repository.succeed(second, now=now + timedelta(seconds=8))


async def test_two_workers_execute_a_named_job_once(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def callback() -> bool:
        calls.append("called")
        started.set()
        await release.wait()
        return True

    first = WorkerIteration(
        sessions,
        (MaintenanceJob("contention", callback),),
        lease_seconds=5,
        owner="worker-a",
    )
    second = WorkerIteration(
        sessions,
        (MaintenanceJob("contention", callback),),
        lease_seconds=5,
        owner="worker-b",
    )
    running = asyncio.create_task(first.run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    assert await second.run_once() is False
    release.set()
    assert await running is True
    assert calls == ["called"]


async def test_long_job_renews_lease_before_another_worker_can_claim(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def callback() -> bool:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return True

    first = WorkerIteration(
        sessions,
        (MaintenanceJob("renewal", callback),),
        lease_seconds=0.3,
        owner="worker-a",
    )
    second = WorkerIteration(
        sessions,
        (MaintenanceJob("renewal", callback),),
        lease_seconds=0.3,
        owner="worker-b",
    )
    running = asyncio.create_task(first.run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.4)
    assert await second.run_once() is False
    release.set()
    assert await running is True
    assert calls == 1


async def test_job_failure_isolated_and_heartbeat_records_failure(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    completed = False

    async def failure() -> bool:
        raise ValueError("synthetic failure")

    async def success() -> bool:
        nonlocal completed
        completed = True
        return True

    iteration = WorkerIteration(
        sessions,
        (
            MaintenanceJob("failure", failure),
            MaintenanceJob("idle", success),
        ),
        lease_seconds=5,
    )
    assert await iteration.run_once()
    assert completed
    async with sessions() as session:
        failed = await session.get(MaintenanceJobState, "failure")
        heartbeat = await session.get(MaintenanceJobState, HEARTBEAT_JOB)
        assert failed is not None and failed.last_error_code == "ValueError"
        assert heartbeat is not None and heartbeat.last_error_code == "ValueError"


async def test_idle_worker_stops_without_an_extra_iteration(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    stop = asyncio.Event()
    calls = 0

    async def callback() -> bool:
        nonlocal calls
        calls += 1
        stop.set()
        return False

    iteration = WorkerIteration(
        sessions,
        (MaintenanceJob("idle", callback),),
        lease_seconds=5,
    )
    await run_worker(iteration, stop, interval_seconds=0.05)
    assert calls == 1


def lease(name: str = "contention") -> MaintenanceLease:
    return MaintenanceLease(name, "worker-a", 1, datetime.now(UTC))


@pytest.mark.parametrize("renewal_error", [None, RuntimeError("renewal failed")])
async def test_running_callback_is_cancelled_when_lease_renewal_fails(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
    renewal_error: RuntimeError | None,
) -> None:
    _, sessions = worker_database
    callback_cancelled = False

    async def callback() -> bool:
        nonlocal callback_cancelled
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            callback_cancelled = True
            raise
        return True

    async def renewal(*_values: object) -> bool:
        if renewal_error is not None:
            raise renewal_error
        return False

    iteration = WorkerIteration(sessions, (), lease_seconds=5)
    monkeypatch.setattr(iteration, "_keep_lease", renewal)
    expected = RuntimeError if renewal_error is not None else MaintenanceLeaseLostError
    with pytest.raises(
        expected, match="renewal failed" if renewal_error else LEASE_LOST
    ):
        await iteration._run_job(MaintenanceJob("contention", callback), lease())
    assert callback_cancelled


async def test_iteration_records_a_lost_completion_lease(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, sessions = worker_database
    iteration = WorkerIteration(sessions, (), lease_seconds=5, owner="worker-a")
    monkeypatch.setattr(iteration, "_jobs", (MaintenanceJob("idle", AsyncMock()),))
    monkeypatch.setattr(iteration, "_claim", AsyncMock(return_value=lease("idle")))
    monkeypatch.setattr(iteration, "_run_job", AsyncMock(return_value=False))
    monkeypatch.setattr(iteration, "_finish", AsyncMock(return_value=False))

    assert await iteration.run_once() is False
    async with sessions() as session:
        heartbeat = await session.get(MaintenanceJobState, HEARTBEAT_JOB)
    assert heartbeat is not None and heartbeat.last_error_code == LEASE_LOST


async def test_keep_lease_stops_after_a_failed_renewal(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, sessions = worker_database
    iteration = WorkerIteration(sessions, (), lease_seconds=0.01)
    renew = AsyncMock(return_value=False)
    monkeypatch.setattr(iteration, "_renew", renew)

    assert not await iteration._keep_lease(lease(), asyncio.Event())
    renew.assert_awaited_once()


async def test_worker_loop_applies_busy_continue_and_idle_backoff() -> None:
    stop = asyncio.Event()

    class SequencedIteration:
        calls = 0

        async def run_once(self) -> bool:
            self.calls += 1
            if self.calls == 3:
                stop.set()
            return self.calls == 1

    iteration = SequencedIteration()
    await run_worker(iteration, stop, interval_seconds=0.001)  # type: ignore[arg-type]
    assert iteration.calls == 3


async def test_successful_early_renewal_preserves_callback_result(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, sessions = worker_database
    iteration = WorkerIteration(sessions, (), lease_seconds=5)

    async def renewed(*_values: object) -> bool:
        return True

    async def callback() -> bool:
        await asyncio.sleep(0)
        return True

    monkeypatch.setattr(iteration, "_keep_lease", renewed)
    assert await iteration._run_job(MaintenanceJob("idle", callback), lease("idle"))

    stopped = asyncio.Event()
    stopped.set()
    assert await WorkerIteration(sessions, (), lease_seconds=5)._keep_lease(
        lease(), stopped
    )


async def test_worker_renewal_fails_after_lease_generation_is_replaced(
    worker_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, sessions = worker_database
    iteration = WorkerIteration(sessions, (), lease_seconds=5, owner="worker-a")
    first = await iteration._claim("contention")
    assert first is not None
    async with sessions() as session, session.begin():
        replacement = await SqlAlchemyMaintenanceLeaseRepository(session).claim(
            "contention",
            "worker-b",
            now=first.expires_at + timedelta(seconds=1),
            lease_seconds=5,
        )
    assert replacement is not None
    assert not await iteration._renew(first)
