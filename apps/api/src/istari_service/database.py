"""Async SQLAlchemy engine and unit-of-work helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import token_bytes

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import istari_service.model_guards as _model_guards  # noqa: F401
from istari_service.audit import AUDIT_KEY_INFO
from istari_service.config import Settings, get_settings
from istari_service.models import Base


def create_database_engine(settings: Settings | None = None) -> AsyncEngine:
    """Build an async engine, retaining one connection for in-memory SQLite."""

    configured = settings or get_settings()
    common: dict[str, object] = {"pool_pre_ping": True}
    if configured.database_url.startswith("sqlite+"):
        if ":memory:" in configured.database_url:
            common["poolclass"] = StaticPool
        common["connect_args"] = {"check_same_thread": False}
    else:
        common.update(
            pool_size=configured.database_pool_size,
            max_overflow=configured.database_max_overflow,
        )
    return create_async_engine(configured.database_url, **common)


def create_session_factory(
    database_engine: AsyncEngine,
    *,
    audit_hmac_key: bytes | None = None,
) -> async_sessionmaker[AsyncSession]:
    key = audit_hmac_key or token_bytes(32)
    return async_sessionmaker(
        database_engine,
        expire_on_commit=False,
        info={AUDIT_KEY_INFO: key},
    )


_settings = get_settings()
engine = create_database_engine(_settings)
SessionFactory = create_session_factory(
    engine,
    audit_hmac_key=_settings.audit_hmac_key_bytes,
)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> AsyncIterator[AsyncSession]:
    """Provide an explicit transaction for scripts and background tasks."""

    async with factory() as session, session.begin():
        yield session


async def create_schema(database_engine: AsyncEngine = engine) -> None:
    """Create tables for isolated tests; production uses Alembic migrations."""

    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database(database_engine: AsyncEngine = engine) -> None:
    await database_engine.dispose()
