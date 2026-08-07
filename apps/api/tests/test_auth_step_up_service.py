"""Password-confirmation step-up behaviour at the authentication boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from istari_service.domain import AccountRecord
from istari_service.errors import AdministrationAccessDenied, AuthenticationFailed
from istari_service.models import UserRole
from test_auth_service import (
    TEST_PASSWORD,
    FakeAuthRepository,
    StubHasher,
    make_account,
    make_service,
    make_session,
)


@pytest.mark.asyncio
async def test_elevate_confirms_an_administrator_password_for_a_bounded_period() -> (
    None
):
    account = make_account(role=UserRole.PLATFORM_ADMIN)
    repository = FakeAuthRepository(account)
    service = make_service(
        repository,
        StubHasher({("stored-hash", TEST_PASSWORD)}),
    )
    session = make_session(account.actor)
    before = datetime.now(UTC)

    until = await service.elevate(session, TEST_PASSWORD)

    assert (
        before + timedelta(seconds=299)
        <= until
        <= datetime.now(UTC) + timedelta(seconds=301)
    )
    assert repository.reset_accounts == [account.actor.id]
    assert repository.elevations == [(session.id, until)]


@pytest.mark.asyncio
async def test_elevate_rejects_non_administrators_without_password_lookup() -> None:
    account = make_account()
    repository = FakeAuthRepository(account)

    with pytest.raises(AdministrationAccessDenied):
        await make_service(repository, StubHasher()).elevate(
            make_session(account.actor), TEST_PASSWORD
        )

    assert repository.lookups == []
    assert repository.elevations == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account", "valid_password", "records_failure"),
    [
        (None, False, False),
        (make_account(role=UserRole.PLATFORM_ADMIN, active=False), True, False),
        (make_account(role=UserRole.PLATFORM_ADMIN), False, True),
        (
            make_account(
                role=UserRole.PLATFORM_ADMIN,
                locked_until=datetime.now(UTC) + timedelta(hours=1),
            ),
            True,
            False,
        ),
    ],
)
async def test_elevate_failures_are_generic_and_never_set_elevation(
    account: AccountRecord | None,
    valid_password: bool,
    records_failure: bool,
) -> None:
    actor = (
        account.actor
        if account is not None
        else make_account(role=UserRole.PLATFORM_ADMIN).actor
    )
    repository = FakeAuthRepository(account)
    pairs = (
        {(account.password_hash, TEST_PASSWORD)}
        if account is not None and valid_password
        else set()
    )

    with pytest.raises(AuthenticationFailed):
        await make_service(repository, StubHasher(pairs)).elevate(
            make_session(actor), TEST_PASSWORD
        )

    assert bool(repository.failures) is records_failure
    assert repository.security_commits == int(records_failure)
    assert repository.elevations == []
