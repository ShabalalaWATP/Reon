"""Atomic persistence coverage for administrator session step-up."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from mist_service.models import Base
from mist_service.repositories.auth import SqlAlchemyAuthRepository
from test_auth_repository import add_session, add_user


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


async def test_set_elevation_atomically_rotates_active_session_credentials(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session)
    active = await add_session(db_session, user, token_hash="pre-step-token")
    repository = SqlAlchemyAuthRepository(db_session)
    until = datetime.now(UTC) + timedelta(minutes=5)

    await repository.set_elevation(
        active.id,
        until,
        token_hash="post-step-token",
        csrf_token_hash="post-step-csrf",
    )
    await db_session.refresh(active)

    assert active.token_hash == "post-step-token"
    assert active.csrf_token_hash == "post-step-csrf"
    assert active.elevated_until == until.replace(tzinfo=None)

    active.revoked_at = datetime.now(UTC)
    await db_session.flush()
    with pytest.raises(LookupError, match="session no longer available"):
        await repository.set_elevation(
            active.id,
            until,
            token_hash="unused",
            csrf_token_hash="unused",
        )
