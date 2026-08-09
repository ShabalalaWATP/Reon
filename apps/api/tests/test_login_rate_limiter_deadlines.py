"""Bounded-failure tests for the durable login-attempt budget."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_test_support import (
    TEST_PASSWORD,
    FakeAuthRepository,
    StubHasher,
    make_service,
)
from istari_service.errors import AuthenticationUnavailable
from istari_service.login_rate_limiter import LoginRateLimitPolicy
from istari_service.repositories.login_rate_limits import SqlAlchemyLoginAttemptLimiter


class BlockingSessionFactory:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.finished = asyncio.Event()

    def __call__(self) -> BlockingSessionFactory:
        return self

    async def __aenter__(self) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.finished.set()

    async def __aexit__(self, *_error: object) -> None:
        return None


async def test_budget_deadline_fails_closed_before_account_or_hash() -> None:
    factory = BlockingSessionFactory()
    limiter = SqlAlchemyLoginAttemptLimiter(
        cast(async_sessionmaker[AsyncSession], factory),
        timeout_seconds=0.05,
    )
    repository = FakeAuthRepository()
    hasher = StubHasher()
    service = make_service(
        repository,
        hasher,
        limiter=limiter,
        policy=LoginRateLimitPolicy(60, 2, 10),
    )

    with pytest.raises(AuthenticationUnavailable):
        await asyncio.wait_for(
            service.login("missing", TEST_PASSWORD),
            timeout=0.5,
        )

    assert factory.started.is_set() and factory.finished.is_set()
    assert repository.lookups == []
    assert hasher.verify_calls == []


async def test_cancellation_cleanup_is_bounded_by_the_budget_deadline() -> None:
    factory = BlockingSessionFactory()
    limiter = SqlAlchemyLoginAttemptLimiter(
        cast(async_sessionmaker[AsyncSession], factory),
        timeout_seconds=0.05,
    )
    operation = asyncio.create_task(
        limiter.consume("source:blocked", LoginRateLimitPolicy(60, 2, 10))
    )
    await factory.started.wait()
    operation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(operation, timeout=0.5)
    assert factory.finished.is_set()
