from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from istari_service.auth_service import AuthService, PasswordHasher, hash_opaque_token
from istari_service.domain import AccountRecord, Actor, SessionRecord
from istari_service.login_rate_limiter import (
    LoginAttemptLimiter,
    LoginRateLimitDecision,
    LoginRateLimitPolicy,
)
from istari_service.models import UserRole

TEST_PASSWORD = "synthetic-passphrase"


def make_account(
    *,
    active: bool = True,
    failed_count: int = 0,
    locked_until: datetime | None = None,
    role: UserRole = UserRole.REQUESTER,
) -> AccountRecord:
    return AccountRecord(
        actor=Actor(
            id=uuid4(),
            username="requester.1@example.test",
            display_name="Synthetic Requester",
            role=role,
            scope="Requesting Area A",
        ),
        password_hash="stored-hash",
        is_active=active,
        failed_login_count=failed_count,
        locked_until=locked_until,
    )


def make_session(actor: Actor | None = None) -> SessionRecord:
    return SessionRecord(
        id=uuid4(),
        actor=actor or make_account().actor,
        csrf_token_hash=hash_opaque_token("initial-csrf"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


class StubHasher(PasswordHasher):
    def __init__(self, valid_pairs: set[tuple[str, str]] | None = None) -> None:
        self.valid_pairs = valid_pairs or set()
        self.hash_calls: list[str] = []
        self.verify_calls: list[tuple[str, str]] = []

    def hash(self, password: str) -> str:
        self.hash_calls.append(password)
        return f"hashed:{password}"

    def verify(self, stored_hash: str, password: str) -> bool:
        self.verify_calls.append((stored_hash, password))
        return (stored_hash, password) in self.valid_pairs


class FakeAuthRepository:
    def __init__(self, account: AccountRecord | None = None) -> None:
        self.account = account
        self.lookups: list[str] = []
        self.failures: list[tuple[int, datetime | None]] = []
        self.reset_accounts: list[UUID] = []
        self.revoked_accounts: list[UUID] = []
        self.created: list[tuple[str, str, datetime]] = []
        self.session_result: SessionRecord | None = None
        self.session_lookups: list[tuple[str, datetime, datetime]] = []
        self.revoked_sessions: list[UUID] = []
        self.rotations: list[tuple[UUID, str]] = []
        self.elevations: list[tuple[UUID, datetime]] = []
        self.security_commits = 0
        self.failure_count = account.failed_login_count if account else 0

    async def find_account(self, username: str) -> AccountRecord | None:
        self.lookups.append(username)
        return self.account

    async def record_failure(
        self,
        account: AccountRecord,
        *,
        now: datetime,
        lockout_threshold: int,
        lockout_seconds: int,
    ) -> None:
        assert account is self.account
        self.failure_count += 1
        locked_until = None
        if self.failure_count >= lockout_threshold:
            self.failure_count = 0
            locked_until = now + timedelta(seconds=lockout_seconds)
        self.failures.append((self.failure_count, locked_until))

    async def reset_failures(self, account: AccountRecord) -> None:
        self.reset_accounts.append(account.actor.id)

    async def revoke_user_sessions(self, account: AccountRecord) -> None:
        self.revoked_accounts.append(account.actor.id)

    async def create_session(
        self,
        account: AccountRecord,
        *,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        self.created.append((token_hash, csrf_token_hash, expires_at))
        return make_session(account.actor)

    async def find_session(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_cutoff: datetime,
        touch: bool = False,
    ) -> SessionRecord | None:
        del touch
        self.session_lookups.append((token_hash, now, idle_cutoff))
        return self.session_result

    async def touch_session(self, session_id: UUID, *, now: datetime) -> None:
        self.session_lookups.append((str(session_id), now, now))

    async def revoke_session(self, session_id: UUID) -> None:
        self.revoked_sessions.append(session_id)

    async def rotate_csrf(self, session_id: UUID, csrf_token_hash: str) -> None:
        self.rotations.append((session_id, csrf_token_hash))

    async def set_elevation(self, session_id: UUID, until: datetime) -> None:
        self.elevations.append((session_id, until))

    async def commit_security_state(self) -> None:
        self.security_commits += 1


class StubLoginLimiter:
    def __init__(self, decision: LoginRateLimitDecision) -> None:
        self.decision = decision
        self.calls: list[tuple[str, LoginRateLimitPolicy]] = []

    async def consume(
        self,
        source_key: str,
        policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision:
        self.calls.append((source_key, policy))
        return self.decision

    async def consume_scope_only(
        self, source_key: str, policy: LoginRateLimitPolicy
    ) -> LoginRateLimitDecision:
        self.calls.append((source_key, policy))
        return self.decision


def make_service(
    repository: FakeAuthRepository,
    hasher: PasswordHasher,
    *,
    threshold: int = 3,
    dummy_hash: str | None = "dummy-hash",
    limiter: LoginAttemptLimiter | None = None,
    policy: LoginRateLimitPolicy | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> AuthService:
    return AuthService(
        repository,
        hasher,
        session_ttl_seconds=600,
        session_idle_seconds=120,
        lockout_threshold=threshold,
        lockout_seconds=300,
        dummy_hash=dummy_hash,
        login_limiter=limiter,
        login_rate_limit_policy=policy,
        password_semaphore=semaphore,
        pseudonym_key=b"p" * 32,
    )
