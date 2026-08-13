"""Distributed login limiter abuse and exact accounting regressions."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from istari_service.database import create_session_factory
from istari_service.login_rate_limit_models import LoginRateLimit
from istari_service.login_rate_limiter import LoginRateLimitPolicy
from istari_service.models import Base
from istari_service.repositories.login_rate_limits import SqlAlchemyLoginAttemptLimiter

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sessions() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


async def test_blocked_source_cannot_exhaust_global_capacity(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    policy = LoginRateLimitPolicy(window_seconds=60, per_source=1, global_limit=3)
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    first = await limiter.consume("source:attacker", policy)
    blocked = [await limiter.consume("source:attacker", policy) for _ in range(5)]
    other = await limiter.consume("source:other", policy)
    async with sessions() as session:
        rows = {
            row.scope_key: row.attempt_count
            for row in await session.scalars(select(LoginRateLimit))
        }

    assert first.allowed
    assert [decision.first_denial for decision in blocked] == [True] + [False] * 4
    assert other.allowed
    assert rows == {"global": 2, "source:attacker": 6, "source:other": 1}


async def test_scope_only_failure_budget_never_double_charges_global(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    policy = LoginRateLimitPolicy(window_seconds=60, per_source=2, global_limit=3)
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    assert (await limiter.consume("source:one", policy)).allowed
    assert (await limiter.consume_scope_only("credential:one", policy)).allowed
    assert (await limiter.consume_scope_only("credential:one", policy)).allowed
    denied = await limiter.consume_scope_only("credential:one", policy)
    repeated = await limiter.consume_scope_only("credential:one", policy)
    assert not denied.allowed and denied.first_denial
    assert not repeated.allowed and not repeated.first_denial
    assert (await limiter.consume("source:two", policy)).allowed
    async with sessions() as session:
        rows = {
            row.scope_key: row.attempt_count
            for row in await session.scalars(select(LoginRateLimit))
        }
    assert rows == {
        "global": 2,
        "source:one": 1,
        "source:two": 1,
        "credential:one": 4,
    }
