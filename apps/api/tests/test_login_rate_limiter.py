"""Distributed login-budget and trusted-proxy security controls."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_test_support import (
    TEST_PASSWORD,
    FakeAuthRepository,
    StubHasher,
    StubLoginLimiter,
    make_service,
)
from mist_service.auth_service import AuthService, PasswordHasher
from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.errors import AuthenticationFailed, AuthenticationRateLimited
from mist_service.login_rate_limit_models import LoginRateLimit
from mist_service.login_rate_limiter import (
    LoginRateLimitDecision,
    LoginRateLimitPolicy,
    LoginRateLimitUnavailable,
)
from mist_service.repositories.login_rate_limits import (
    SqlAlchemyLoginAttemptLimiter,
    _dialect_insert,
    _retry_after,
)

PSEUDONYM_KEY = b"p" * 32


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


async def test_source_limit_is_shared_between_database_sessions(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    policy = LoginRateLimitPolicy(window_seconds=60, per_source=2, global_limit=10)
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    decisions = [await limiter.consume("source:shared", policy) for _ in range(3)]

    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert 1 <= decisions[-1].retry_after_seconds <= 60


async def test_global_budget_bounds_distributed_hash_admission_and_cleanup_runs(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        session.add(
            LoginRateLimit(
                scope_key="source:expired",
                window_started_at=now - timedelta(hours=2),
                attempt_count=1,
                expires_at=now - timedelta(seconds=1),
            )
        )
    policy = LoginRateLimitPolicy(window_seconds=60, per_source=10, global_limit=2)
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    decisions = [
        await limiter.consume(source, policy)
        for source in ("source:one", "source:two", "source:three")
    ]
    async with sessions() as session:
        expired = await session.get(LoginRateLimit, "source:expired")
        keys = set(await session.scalars(select(LoginRateLimit.scope_key)))

    assert expired is None
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert keys == {"global", "source:one", "source:two", "source:three"}


async def test_budget_is_committed_before_slow_password_work(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    class BlockingHasher(PasswordHasher):
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()

        def hash(self, password: str) -> str:
            return f"hash:{password}"

        def verify(self, _stored_hash: str, _password: str) -> bool:
            self.started.set()
            assert self.release.wait(timeout=3)
            return False

    policy = LoginRateLimitPolicy(window_seconds=60, per_source=10, global_limit=10)
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    hasher = BlockingHasher()
    service = AuthService(
        FakeAuthRepository(),
        hasher,
        session_ttl_seconds=600,
        session_idle_seconds=120,
        dummy_hash="dummy-hash",
        login_limiter=limiter,
        login_rate_limit_policy=policy,
        pseudonym_key=PSEUDONYM_KEY,
    )

    login = asyncio.create_task(service.login("missing", TEST_PASSWORD))
    assert await asyncio.to_thread(hasher.started.wait, 1)
    async with sessions() as session:
        counts = {
            row.scope_key: row.attempt_count
            for row in await session.scalars(select(LoginRateLimit))
        }
    second = await asyncio.wait_for(
        limiter.consume("source:second", policy),
        timeout=1,
    )
    hasher.release.set()

    assert counts["source:unit-test"] == 1
    assert counts["global"] == 1
    assert second.allowed
    with pytest.raises(AuthenticationFailed):
        await login


async def test_cancellation_waits_for_durable_budget_operation(
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)
    started = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()

    async def controlled_consume(
        _source_key: str,
        _policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        started.set()
        await release.wait()
        completed.set()
        return LoginRateLimitDecision(True)

    monkeypatch.setattr(limiter, "_consume_durably", controlled_consume)
    operation = asyncio.create_task(
        limiter.consume("source:cancelled", LoginRateLimitPolicy(60, 2, 10))
    )
    await started.wait()
    operation.cancel()
    await asyncio.sleep(0)
    assert not operation.done()
    release.set()

    with pytest.raises(asyncio.CancelledError):
        await operation
    assert completed.is_set()


async def test_postgresql_limiter_sets_transaction_local_timeouts(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    class FakePostgresSession:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def get_bind(self) -> SimpleNamespace:
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def scalar(self, statement: object) -> str:
            self.statements.append(str(statement))
            return "2400ms"

    session = FakePostgresSession()
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=3)
    await limiter._configure_database_timeouts(cast(AsyncSession, session))

    assert len(session.statements) == 2
    assert all("set_config" in statement for statement in session.statements)


async def test_database_timeout_is_mapped_to_limiter_unavailable(
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = SqlAlchemyLoginAttemptLimiter(sessions, timeout_seconds=1)

    async def timed_out(
        _source_key: str,
        _policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        raise TimeoutError

    monkeypatch.setattr(limiter, "_consume_durably", timed_out)
    with pytest.raises(LoginRateLimitUnavailable):
        await limiter.consume("source:timeout", LoginRateLimitPolicy(60, 2, 10))


def test_dialect_statements_and_retry_bounds_are_explicit() -> None:
    table = LoginRateLimit.__table__
    postgres_sql = str(
        _dialect_insert("postgresql", table).compile(dialect=postgresql.dialect())
    )
    sqlite_sql = str(_dialect_insert("sqlite", table).compile(dialect=sqlite.dialect()))
    assert "INSERT INTO login_rate_limits" in postgres_sql
    assert "INSERT INTO login_rate_limits" in sqlite_sql
    with pytest.raises(RuntimeError, match="PostgreSQL or SQLite"):
        _dialect_insert("unsupported", table)

    now = datetime.now(UTC)
    assert _retry_after(now, now + timedelta(seconds=10), 60) == 60
    assert _retry_after(now, now - timedelta(minutes=2), 60) == 1


async def test_login_budget_rejects_before_account_lookup_or_password_hash() -> None:
    repository = FakeAuthRepository()
    hasher = StubHasher()
    limiter = StubLoginLimiter(LoginRateLimitDecision(False, 17))
    policy = LoginRateLimitPolicy(60, 2, 10)
    service = make_service(repository, hasher, limiter=limiter, policy=policy)

    with pytest.raises(AuthenticationRateLimited) as raised:
        await service.login(
            "missing@example.test", TEST_PASSWORD, source_key="source:x"
        )

    assert raised.value.response_headers == {"Retry-After": "17"}
    assert limiter.calls == [("source:x", policy)]
    assert repository.security_commits == 0
    assert repository.lookups == []
    assert hasher.verify_calls == []


async def test_login_limiter_requires_policy_and_persists_unknown_attempt() -> None:
    allowed = StubLoginLimiter(LoginRateLimitDecision(True))
    repository = FakeAuthRepository()
    hasher = StubHasher()
    with pytest.raises(RuntimeError, match="policy is required"):
        await make_service(repository, hasher, limiter=allowed).login(
            "missing@example.test",
            TEST_PASSWORD,
        )

    policy = LoginRateLimitPolicy(60, 2, 10)
    service = make_service(
        repository,
        hasher,
        limiter=allowed,
        policy=policy,
        semaphore=asyncio.Semaphore(1),
    )
    with pytest.raises(AuthenticationFailed):
        await service.login("missing@example.test", TEST_PASSWORD)
    assert repository.security_commits == 0
    assert hasher.verify_calls == [("dummy-hash", TEST_PASSWORD)]
