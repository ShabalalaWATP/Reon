"""Focused regression coverage for throttled session activity writes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from istari_service.models import Base, Session, User, UserRole
from istari_service.repositories.auth import SqlAlchemyAuthRepository


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_find_session_does_not_rewrite_a_recent_last_seen(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    user = User(
        username="recent-session@example.test",
        display_name="Recent Session",
        password_hash="stored-hash",
        role=UserRole.REQUESTER,
        scope="Requesting Area A",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    recent = now - timedelta(minutes=1)
    stored = Session(
        user_id=user.id,
        token_hash="recent-token-hash",
        csrf_token_hash="csrf-hash",
        credential_version=user.credential_version,
        last_seen_at=recent,
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(stored)
    await db_session.flush()

    result = await SqlAlchemyAuthRepository(db_session).find_session(
        stored.token_hash,
        now=now,
        idle_cutoff=now - timedelta(minutes=5),
    )

    assert result is not None
    assert stored.last_seen_at == recent
