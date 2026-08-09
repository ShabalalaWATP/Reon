from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from auth_test_support import (
    TEST_PASSWORD,
    FakeAuthRepository,
    StubHasher,
    make_account,
    make_service,
    make_session,
)
from istari_service.auth_service import (
    DUMMY_HASH_INPUT,
    PasswordHasher,
    hash_opaque_token,
)
from istari_service.domain import AccountRecord
from istari_service.errors import AuthenticationFailed, SessionRequired


def test_hash_opaque_token_is_stable_sha256() -> None:
    assert hash_opaque_token("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert hash_opaque_token("abc") != hash_opaque_token("ABC")


def test_password_hasher_uses_argon2id_and_rejects_bad_inputs() -> None:
    hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    stored = hasher.hash(TEST_PASSWORD)

    assert stored.startswith("$argon2id$")
    assert hasher.verify(stored, TEST_PASSWORD)
    assert not hasher.verify(stored, "wrong-passphrase")
    assert not hasher.verify("not-an-argon-hash", TEST_PASSWORD)


def test_constructor_builds_dummy_hash_when_one_is_not_supplied() -> None:
    hasher = StubHasher()
    make_service(FakeAuthRepository(), hasher, dummy_hash=None)
    assert hasher.hash_calls == [DUMMY_HASH_INPUT]


@pytest.mark.asyncio
async def test_login_normalises_username_and_rotates_existing_sessions() -> None:
    account = make_account(locked_until=datetime.now(UTC) - timedelta(seconds=1))
    repository = FakeAuthRepository(account)
    hasher = StubHasher({("stored-hash", TEST_PASSWORD)})
    service = make_service(repository, hasher)
    before = datetime.now(UTC)

    result = await service.login("  REQUESTER.1@EXAMPLE.TEST ", TEST_PASSWORD)

    after = datetime.now(UTC)
    assert repository.lookups == ["requester.1@example.test"]
    assert repository.reset_accounts == [account.actor.id]
    assert repository.revoked_accounts == [account.actor.id]
    assert result.session.actor == account.actor
    assert result.session_token and result.csrf_token
    token_hash, csrf_hash, expires_at = repository.created[0]
    assert token_hash == hash_opaque_token(result.session_token)
    assert csrf_hash == hash_opaque_token(result.csrf_token)
    assert (
        before + timedelta(seconds=600) <= expires_at <= after + timedelta(seconds=600)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account", "valid_pair", "records_failure"),
    [
        (None, False, False),
        (make_account(), False, True),
        (make_account(active=False), True, False),
        (
            make_account(locked_until=datetime.now(UTC) + timedelta(hours=1)),
            True,
            False,
        ),
    ],
)
async def test_login_failures_are_generic(
    account: AccountRecord | None,
    valid_pair: bool,
    records_failure: bool,
) -> None:
    repository = FakeAuthRepository(account)
    stored_hash = account.password_hash if account else "dummy-hash"
    pairs = {(stored_hash, TEST_PASSWORD)} if valid_pair else set()
    service = make_service(repository, StubHasher(pairs))

    with pytest.raises(AuthenticationFailed) as raised:
        await service.login("requester.1@example.test", TEST_PASSWORD)

    assert str(raised.value) == "Unable to sign in with those credentials."
    assert bool(repository.failures) is records_failure
    assert repository.security_commits == int(records_failure)
    assert repository.created == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("starting_count", "expected_count", "expect_lock"),
    [(0, 1, False), (2, 0, True)],
)
async def test_failed_password_counts_and_locks_at_threshold(
    starting_count: int,
    expected_count: int,
    expect_lock: bool,
) -> None:
    account = make_account(failed_count=starting_count)
    repository = FakeAuthRepository(account)
    service = make_service(repository, StubHasher())
    before = datetime.now(UTC)

    with pytest.raises(AuthenticationFailed):
        await service.login(account.actor.username, TEST_PASSWORD)

    count, locked_until = repository.failures[0]
    assert repository.security_commits == 1
    assert count == expected_count
    assert (locked_until is not None) is expect_lock
    if locked_until is not None:
        assert locked_until >= before + timedelta(seconds=299)


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, ""])
async def test_authenticate_requires_a_token(token: str | None) -> None:
    repository = FakeAuthRepository()
    with pytest.raises(SessionRequired):
        await make_service(repository, StubHasher()).authenticate(token)
    assert repository.session_lookups == []
    assert repository.security_commits == 0


@pytest.mark.asyncio
async def test_authenticate_rejects_unknown_or_expired_repository_result() -> None:
    repository = FakeAuthRepository()
    with pytest.raises(SessionRequired):
        await make_service(repository, StubHasher()).authenticate("opaque-token")

    token_hash, now, idle_cutoff = repository.session_lookups[0]
    assert repository.security_commits == 1
    assert token_hash == hash_opaque_token("opaque-token")
    assert timedelta(seconds=119) <= now - idle_cutoff <= timedelta(seconds=121)


@pytest.mark.asyncio
async def test_authenticate_returns_repository_session() -> None:
    repository = FakeAuthRepository()
    repository.session_result = make_session()
    result = await make_service(repository, StubHasher()).authenticate("opaque-token")
    assert result is repository.session_result
    assert repository.security_commits == 0


@pytest.mark.asyncio
async def test_logout_and_csrf_refresh_delegate_hashed_values() -> None:
    repository = FakeAuthRepository()
    service = make_service(repository, StubHasher())
    session = make_session()

    await service.logout(session)
    refreshed = await service.refresh_csrf(session)

    assert repository.revoked_sessions == [session.id]
    assert repository.rotations == [(session.id, hash_opaque_token(refreshed))]
    assert refreshed != repository.rotations[0][1]
