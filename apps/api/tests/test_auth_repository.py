from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from istari_service.domain import AccountRecord, Actor
from istari_service.models import Base, Session, User, UserRole
from istari_service.repositories.auth import (
    SqlAlchemyAuthRepository,
    account_from_user,
    actor_from_user,
)


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


async def add_user(
    session: AsyncSession,
    *,
    active: bool = True,
    credential_version: int = 1,
    locked_until: datetime | None = None,
) -> User:
    username = f"requester.{uuid4().hex}@example.test"
    user = User(
        username=username,
        email=username,
        display_name="Synthetic Requester",
        password_hash="stored-hash",
        role=UserRole.REQUESTER,
        scope="Requesting Area A",
        is_active=active,
        credential_version=credential_version,
        locked_until=locked_until,
    )
    session.add(user)
    await session.flush()
    return user


async def add_session(
    session: AsyncSession,
    user: User,
    *,
    token_hash: str = "token-hash",  # noqa: S107 - synthetic session hash
    now: datetime | None = None,
) -> Session:
    current = now or datetime.now(UTC)
    stored = Session(
        user_id=user.id,
        token_hash=token_hash,
        csrf_token_hash="csrf-hash",
        credential_version=user.credential_version,
        created_at=current,
        last_seen_at=current - timedelta(minutes=1),
        expires_at=current + timedelta(hours=1),
    )
    session.add(stored)
    await session.flush()
    return stored


def orphan_account() -> AccountRecord:
    return AccountRecord(
        actor=Actor(
            id=uuid4(),
            username="missing@example.test",
            display_name="Missing User",
            role=UserRole.REQUESTER,
            scope="Requesting Area A",
        ),
        password_hash="stored-hash",
        is_active=True,
        failed_login_count=0,
        locked_until=None,
    )


@pytest.mark.asyncio
async def test_actor_and_account_records_normalise_datetimes(
    db_session: AsyncSession,
) -> None:
    naive_lock = datetime(2030, 1, 2, 3, 4, 5)  # noqa: DTZ001
    user = await add_user(db_session, locked_until=naive_lock)

    actor = actor_from_user(user)
    account = account_from_user(user)

    assert actor.id == user.id
    assert actor.username == user.username
    assert actor.role is UserRole.REQUESTER
    assert account.actor == actor
    assert account.locked_until == naive_lock.replace(tzinfo=UTC)
    user.locked_until = datetime(2030, 1, 2, tzinfo=UTC) + timedelta(hours=1)
    assert account_from_user(user).locked_until == datetime(2030, 1, 2, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_find_account_returns_record_none(db_session: AsyncSession) -> None:
    user = await add_user(db_session)
    repository = SqlAlchemyAuthRepository(db_session)

    found = await repository.find_account(user.username)

    assert found is not None
    assert found.actor.id == user.id
    assert await repository.find_account("absent@example.test") is None


@pytest.mark.asyncio
async def test_failure_state_updates_and_missing_accounts_are_safe(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session)
    repository = SqlAlchemyAuthRepository(db_session)
    account = account_from_user(user)
    now = datetime.now(UTC)

    for _ in range(4):
        await repository.record_failure(
            account,
            now=now,
            lockout_threshold=5,
            lockout_seconds=600,
        )
    await db_session.refresh(user)
    assert user.failed_login_count == 4
    assert user.locked_until is None

    await repository.record_failure(
        account,
        now=now,
        lockout_threshold=5,
        lockout_seconds=600,
    )
    await db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is not None
    assert user.locked_until.replace(tzinfo=UTC) == now + timedelta(minutes=10)

    await repository.reset_failures(account)
    assert user.failed_login_count == 0
    assert user.locked_until is None

    missing = orphan_account()
    await repository.record_failure(
        missing,
        now=now,
        lockout_threshold=5,
        lockout_seconds=600,
    )
    await repository.reset_failures(missing)


@pytest.mark.asyncio
async def test_revoke_user_sessions_only_changes_active_rows(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session)
    active = await add_session(db_session, user, token_hash="active-token")
    already_revoked = await add_session(db_session, user, token_hash="revoked-token")
    original = datetime.now(UTC) - timedelta(days=1)
    already_revoked.revoked_at = original
    await db_session.flush()

    await SqlAlchemyAuthRepository(db_session).revoke_user_sessions(
        account_from_user(user)
    )
    await db_session.refresh(active)
    await db_session.refresh(already_revoked)

    assert active.revoked_at is not None
    assert already_revoked.revoked_at is not None
    assert already_revoked.revoked_at.replace(tzinfo=UTC) == original


@pytest.mark.asyncio
async def test_create_session_persists_hashes_and_credential_version(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session, credential_version=7)
    repository = SqlAlchemyAuthRepository(db_session)
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    result = await repository.create_session(
        account_from_user(user),
        token_hash="new-token-hash",
        csrf_token_hash="new-csrf-hash",
        expires_at=expires_at,
    )
    stored = await db_session.get(Session, result.id)

    assert stored is not None
    assert stored.token_hash == "new-token-hash"
    assert stored.csrf_token_hash == "new-csrf-hash"
    assert stored.credential_version == 7
    assert result.actor.id == user.id


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [False, True])
async def test_create_session_rechecks_account_availability(
    db_session: AsyncSession,
    missing: bool,
) -> None:
    repository = SqlAlchemyAuthRepository(db_session)
    if missing:
        account = orphan_account()
    else:
        account = account_from_user(await add_user(db_session, active=False))

    with pytest.raises(LookupError, match="account no longer available"):
        await repository.create_session(
            account,
            token_hash="new-token-hash",
            csrf_token_hash="new-csrf-hash",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


@pytest.mark.asyncio
async def test_find_session_returns_active_session_and_touches_last_seen(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    user = await add_user(db_session)
    stored = await add_session(db_session, user, now=now)
    stored.last_seen_at = now - timedelta(minutes=3)

    result = await SqlAlchemyAuthRepository(db_session).find_session(
        stored.token_hash,
        now=now,
        idle_cutoff=now - timedelta(minutes=5),
    )

    assert result is not None
    assert result.id == stored.id
    assert result.actor.id == user.id
    assert result.expires_at.tzinfo is UTC
    assert stored.last_seen_at == now
    assert stored.revoked_at is None


@pytest.mark.asyncio
async def test_find_session_returns_none_when_hash_is_unknown(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    result = await SqlAlchemyAuthRepository(db_session).find_session(
        "unknown",
        now=now,
        idle_cutoff=now - timedelta(minutes=5),
    )
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_reason",
    ["revoked", "expired", "idle", "disabled", "credential_changed"],
)
async def test_find_session_rejects_every_invalid_state(
    db_session: AsyncSession,
    invalid_reason: str,
) -> None:
    now = datetime.now(UTC)
    user = await add_user(db_session)
    stored = await add_session(db_session, user, now=now)
    idle_cutoff = now - timedelta(minutes=5)
    original_revocation = now - timedelta(days=1)
    if invalid_reason == "revoked":
        stored.revoked_at = original_revocation
    elif invalid_reason == "expired":
        stored.expires_at = now
    elif invalid_reason == "idle":
        stored.last_seen_at = idle_cutoff
    elif invalid_reason == "disabled":
        user.is_active = False
    else:
        user.credential_version += 1
    await db_session.flush()

    result = await SqlAlchemyAuthRepository(db_session).find_session(
        stored.token_hash,
        now=now,
        idle_cutoff=idle_cutoff,
    )

    assert result is None
    assert stored.revoked_at is not None
    if invalid_reason == "revoked":
        assert stored.revoked_at == original_revocation
    else:
        assert stored.revoked_at == now


@pytest.mark.asyncio
async def test_revoke_session_is_idempotent_and_missing_is_safe(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session)
    stored = await add_session(db_session, user)
    repository = SqlAlchemyAuthRepository(db_session)

    await repository.revoke_session(stored.id)
    first_revocation = stored.revoked_at
    await repository.revoke_session(stored.id)
    await repository.revoke_session(uuid4())

    assert first_revocation is not None
    assert stored.revoked_at == first_revocation


@pytest.mark.asyncio
async def test_rotate_csrf_updates_active_session_and_rejects_unavailable(
    db_session: AsyncSession,
) -> None:
    user = await add_user(db_session)
    active = await add_session(db_session, user, token_hash="active-token")
    revoked = await add_session(db_session, user, token_hash="revoked-token")
    revoked.revoked_at = datetime.now(UTC)
    repository = SqlAlchemyAuthRepository(db_session)

    await repository.rotate_csrf(active.id, "rotated-hash")
    assert active.csrf_token_hash == "rotated-hash"

    with pytest.raises(LookupError, match="session no longer available"):
        await repository.rotate_csrf(revoked.id, "unused")
    with pytest.raises(LookupError, match="session no longer available"):
        await repository.rotate_csrf(uuid4(), "unused")
