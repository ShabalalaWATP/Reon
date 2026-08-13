"""Atomic PostgreSQL and SQLite login rate-limit persistence."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.login_rate_limit_models import LoginRateLimit
from istari_service.login_rate_limiter import (
    LoginRateLimitDecision,
    LoginRateLimitPolicy,
    LoginRateLimitUnavailable,
)

GLOBAL_SCOPE = "global"


class SqlAlchemyLoginAttemptLimiter:
    """Consume login budgets in a cancellation-shielded short transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        timeout_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._timeout_seconds = timeout_seconds

    async def consume(
        self,
        source_key: str,
        policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        operation = asyncio.create_task(self._consume_durably(source_key, policy))
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            # The operation owns its deadline. A disconnected caller cannot
            # discard a fast accepted attempt or leave an unbounded task.
            with suppress(TimeoutError, SQLAlchemyError):
                await asyncio.shield(operation)
            raise
        except (TimeoutError, SQLAlchemyError) as error:
            raise LoginRateLimitUnavailable() from error

    async def consume_scope_only(
        self, scope_key: str, policy: LoginRateLimitPolicy
    ) -> LoginRateLimitDecision:
        operation = asyncio.create_task(self._consume_scope_durably(scope_key, policy))
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            with suppress(TimeoutError, SQLAlchemyError):
                await asyncio.shield(operation)
            raise
        except (TimeoutError, SQLAlchemyError) as error:
            raise LoginRateLimitUnavailable() from error

    async def _consume_scope_durably(
        self, scope_key: str, policy: LoginRateLimitPolicy
    ) -> LoginRateLimitDecision:
        async with asyncio.timeout(self._timeout_seconds):
            async with self._session_factory() as session, session.begin():
                await self._configure_database_timeouts(session)
                now = datetime.now(UTC)
                count, started = await self._consume_scope(
                    session, scope_key, now, policy.window_seconds
                )
                retry = (
                    _retry_after(now, started, policy.window_seconds)
                    if count > policy.per_source
                    else 0
                )
                return LoginRateLimitDecision(
                    not retry, retry, count == policy.per_source + 1
                )

    async def _consume_durably(
        self,
        source_key: str,
        policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        async with asyncio.timeout(self._timeout_seconds):
            async with self._session_factory() as session, session.begin():
                await self._configure_database_timeouts(session)
                return await self._consume_in_transaction(session, source_key, policy)

    async def _configure_database_timeouts(self, session: AsyncSession) -> None:
        if session.get_bind().dialect.name != "postgresql":
            return
        timeout_ms = max(100, int(self._timeout_seconds * 800))
        timeout_value = f"{timeout_ms}ms"
        for setting in ("statement_timeout", "lock_timeout"):
            await session.scalar(select(func.set_config(setting, timeout_value, True)))

    async def _consume_in_transaction(
        self,
        session: AsyncSession,
        source_key: str,
        policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        now = datetime.now(UTC)
        source_count, source_start = await self._consume_scope(
            session,
            source_key,
            now,
            policy.window_seconds,
        )
        source_retry = (
            _retry_after(now, source_start, policy.window_seconds)
            if source_count > policy.per_source
            else 0
        )
        if source_retry:
            return LoginRateLimitDecision(
                False, source_retry, source_count == policy.per_source + 1
            )
        global_count, global_start = await self._consume_scope(
            session, GLOBAL_SCOPE, now, policy.window_seconds
        )
        if global_count == 1:
            await session.execute(
                delete(LoginRateLimit).where(
                    LoginRateLimit.expires_at <= now,
                    LoginRateLimit.scope_key != GLOBAL_SCOPE,
                )
            )
        retries = [
            _retry_after(now, start, policy.window_seconds)
            for count, limit, start in (
                (global_count, policy.global_limit, global_start),
            )
            if count > limit
        ]
        return LoginRateLimitDecision(
            allowed=not retries,
            retry_after_seconds=max(retries, default=0),
            first_denial=global_count == policy.global_limit + 1,
        )

    async def _consume_scope(
        self,
        session: AsyncSession,
        scope_key: str,
        now: datetime,
        window_seconds: int,
    ) -> tuple[int, datetime]:
        cutoff = now - timedelta(seconds=window_seconds)
        expires_at = now + timedelta(seconds=max(3_600, window_seconds * 2))
        table = LoginRateLimit.__table__
        values = {
            "scope_key": scope_key,
            "window_started_at": now,
            "attempt_count": 1,
            "expires_at": expires_at,
        }
        dialect = session.get_bind().dialect.name
        statement: Any = _dialect_insert(dialect, table).values(**values)
        expired = table.c.window_started_at <= cutoff
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.scope_key],
            set_={
                "window_started_at": case(
                    (expired, now), else_=table.c.window_started_at
                ),
                "attempt_count": case((expired, 1), else_=table.c.attempt_count + 1),
                "expires_at": case((expired, expires_at), else_=table.c.expires_at),
            },
        ).returning(table.c.attempt_count, table.c.window_started_at)
        count, started_at = (await session.execute(statement)).one()
        return int(count), _as_utc(started_at)


def _retry_after(now: datetime, started_at: datetime, window_seconds: int) -> int:
    remaining = window_seconds - (now - _as_utc(started_at)).total_seconds()
    return max(1, min(window_seconds, ceil(remaining)))


def _dialect_insert(dialect: str, table: Any) -> Any:
    if dialect == "postgresql":
        return postgres_insert(table)
    if dialect == "sqlite":
        return sqlite_insert(table)
    raise RuntimeError("login limiting requires PostgreSQL or SQLite")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
