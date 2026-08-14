"""Persistence checks for secure session-context rotation."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from istari_service.compliance_models import SecurityEvent
from istari_service.domain import SessionRecord
from istari_service.identity_context_service import IdentityContextService
from istari_service.models import Base, IdentityContext, Session, User, UserRole
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


async def test_switch_context_is_entitled_rotated_and_optimistic(
    db_session: AsyncSession,
) -> None:
    username = f"analyst.{uuid4().hex}@example.test"
    user = User(
        username=username,
        email=username,
        display_name="Synthetic Analyst",
        password_hash="stored-hash",
        role=UserRole.DELIVERY_SPECIALIST,
        scope="SSG Team",
        customer_context_enabled=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    stored = Session(
        user_id=user.id,
        token_hash="token-hash",
        csrf_token_hash="csrf-hash",
        credential_version=user.credential_version,
        active_context=IdentityContext.STAFF,
        last_seen_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(stored)
    await db_session.flush()
    repository = SqlAlchemyAuthRepository(db_session)

    switched = await repository.switch_context(
        stored.id,
        context=IdentityContext.CUSTOMER,
        expected_context_version=1,
        token_hash="rotated-token-hash",
        csrf_token_hash="rotated-csrf-hash",
    )

    assert switched.active_context is IdentityContext.CUSTOMER
    assert switched.context_version == 2
    assert switched.actor.role is UserRole.REQUESTER
    assert switched.actor.organisation_unit_ids == frozenset()
    assert stored.token_hash == "rotated-token-hash"
    assert stored.csrf_token_hash == "rotated-csrf-hash"
    with pytest.raises(PermissionError, match="identity context is unavailable"):
        await repository.switch_context(
            stored.id,
            context=IdentityContext.STAFF,
            expected_context_version=1,
            token_hash="stale-token",
            csrf_token_hash="stale-csrf",
        )


async def test_success_audit_failure_rolls_back_undisclosed_rotated_secrets(
    db_session: AsyncSession,
) -> None:
    username = f"atomic.{uuid4().hex}@example.test"
    user = User(
        username=username,
        email=username,
        display_name="Synthetic Atomic User",
        password_hash="stored-hash",
        role=UserRole.DELIVERY_SPECIALIST,
        scope="SSG Team",
        customer_context_enabled=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    stored = Session(
        user_id=user.id,
        token_hash="original-token-hash",
        csrf_token_hash="original-csrf-hash",
        credential_version=user.credential_version,
        active_context=IdentityContext.STAFF,
        last_seen_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(stored)
    await db_session.commit()
    session_id = stored.id
    account = await SqlAlchemyAuthRepository(db_session).find_account(username)
    assert account is not None
    record = SessionRecord(
        id=session_id,
        actor=account.actor,
        csrf_token_hash=stored.csrf_token_hash,
        expires_at=stored.expires_at,
        active_context=IdentityContext.STAFF,
        available_contexts=(IdentityContext.STAFF, IdentityContext.CUSTOMER),
        context_version=1,
    )
    failing_events = SimpleNamespace(
        build=lambda _command: (_ for _ in ()).throw(RuntimeError("audit failed"))
    )
    service = IdentityContextService(
        SqlAlchemyAuthRepository(db_session), failing_events
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        await service.switch(record, IdentityContext.CUSTOMER)
    await db_session.rollback()

    persisted = await db_session.get(Session, session_id)
    assert persisted is not None
    assert persisted.active_context is IdentityContext.STAFF
    assert persisted.context_version == 1
    assert persisted.token_hash == "original-token-hash"
    assert persisted.csrf_token_hash == "original-csrf-hash"
    assert await db_session.scalar(select(SecurityEvent)) is None
