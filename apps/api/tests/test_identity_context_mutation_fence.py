"""Session context-version mutation fence, including PostgreSQL ordering."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mist_service.models import Base, IdentityContext, Session, User, UserRole
from mist_service.repositories.auth import SqlAlchemyAuthRepository


async def test_mutation_fence_rejects_a_stale_context_version() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            user = User(
                username=f"fence.{uuid4().hex}@example.test",
                email=f"fence.{uuid4().hex}@example.test",
                display_name="Synthetic Fence User",
                password_hash="synthetic",
                role=UserRole.DELIVERY_SPECIALIST,
                scope="OSG Team",
                customer_context_enabled=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            stored = Session(
                user_id=user.id,
                token_hash=uuid4().hex,
                csrf_token_hash=uuid4().hex,
                credential_version=user.credential_version,
                active_context=IdentityContext.CUSTOMER,
                context_version=2,
                last_seen_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            session.add(stored)
            await session.flush()
            session_id = stored.id
        async with sessions() as session, session.begin():
            repository = SqlAlchemyAuthRepository(session)
            assert not await repository.lock_mutation_context(
                session_id, expected_context_version=1
            )
            assert await repository.lock_mutation_context(
                session_id, expected_context_version=2
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("switch_first", [False, True])
async def test_postgresql_context_switch_and_mutation_have_one_serial_order(
    switch_first: bool,
) -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"context_fence_{uuid4().hex}"
    session_id = uuid4()
    first_locked = asyncio.Event()
    release_first = asyncio.Event()
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text(f"SET LOCAL search_path TO {schema}"))
            await connection.execute(
                text(
                    "CREATE TABLE sessions (id uuid PRIMARY KEY, "
                    "context_version integer NOT NULL, revoked_at timestamptz)"
                )
            )
            await connection.execute(text("CREATE TABLE effects (id uuid PRIMARY KEY)"))
            await connection.execute(
                text("INSERT INTO sessions VALUES (:id, 1, NULL)"), {"id": session_id}
            )

        async def mutation() -> bool:
            async with sessions() as session, session.begin():
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))
                allowed = await SqlAlchemyAuthRepository(session).lock_mutation_context(
                    session_id, expected_context_version=1
                )
                if not allowed:
                    return False
                first_locked.set()
                if not switch_first:
                    await release_first.wait()
                await session.execute(
                    text("INSERT INTO effects VALUES (:id)"), {"id": uuid4()}
                )
                return True

        async def switch() -> None:
            async with sessions() as session, session.begin():
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))
                await session.execute(
                    text(
                        "UPDATE sessions SET context_version=2 "
                        "WHERE id=:id AND context_version=1"
                    ),
                    {"id": session_id},
                )
                first_locked.set()
                if switch_first:
                    await release_first.wait()

        first = asyncio.create_task(switch() if switch_first else mutation())
        await asyncio.wait_for(first_locked.wait(), timeout=5)
        second = asyncio.create_task(mutation() if switch_first else switch())
        await asyncio.sleep(0.1)
        assert not second.done()
        release_first.set()
        results = await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
        mutation_committed = results[1] if switch_first else results[0]
        async with sessions() as session:
            await session.execute(text(f"SET search_path TO {schema}"))
            effect_count = await session.scalar(text("SELECT count(*) FROM effects"))
        assert bool(effect_count) is bool(mutation_committed)
        assert bool(mutation_committed) is (not switch_first)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
