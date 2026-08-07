"""Password and opaque-session authentication use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol
from uuid import UUID

from anyio import to_thread
from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2 import Type
from argon2.exceptions import Argon2Error, InvalidHashError

from istari_service.domain import AccountRecord, SessionRecord
from istari_service.errors import (
    AdministrationAccessDenied,
    AuthenticationFailed,
    SessionRequired,
)
from istari_service.models import UserRole

DUMMY_HASH_INPUT = "local-unknown-account-input"


def hash_opaque_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class PasswordHasher:
    """Argon2id wrapper kept replaceable for fast deterministic tests."""

    def __init__(
        self,
        *,
        time_cost: int = 3,
        memory_cost: int = 65_536,
        parallelism: int = 4,
    ) -> None:
        self._hasher = ArgonPasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(stored_hash, password)
        except (Argon2Error, InvalidHashError):
            return False


class AuthRepository(Protocol):
    async def find_account(self, username: str) -> AccountRecord | None: ...

    async def record_failure(
        self,
        account: AccountRecord,
        *,
        now: datetime,
        lockout_threshold: int,
        lockout_seconds: int,
    ) -> None: ...

    async def reset_failures(self, account: AccountRecord) -> None: ...

    async def revoke_user_sessions(self, account: AccountRecord) -> None: ...

    async def create_session(
        self,
        account: AccountRecord,
        *,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord: ...

    async def find_session(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_cutoff: datetime,
    ) -> SessionRecord | None: ...

    async def revoke_session(self, session_id: UUID) -> None: ...

    async def rotate_csrf(self, session_id: UUID, csrf_token_hash: str) -> None: ...

    async def set_elevation(self, session_id: UUID, until: datetime) -> None: ...

    async def commit_security_state(self) -> None: ...


@dataclass(frozen=True, slots=True)
class LoginResult:
    session: SessionRecord
    session_token: str
    csrf_token: str


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        password_hasher: PasswordHasher,
        *,
        session_ttl_seconds: int,
        session_idle_seconds: int,
        lockout_threshold: int = 5,
        lockout_seconds: int = 900,
        admin_elevation_seconds: int = 300,
        dummy_hash: str | None = None,
    ) -> None:
        self._repository = repository
        self._hasher = password_hasher
        self._session_ttl = session_ttl_seconds
        self._session_idle = session_idle_seconds
        self._lockout_threshold = lockout_threshold
        self._lockout_seconds = lockout_seconds
        self._admin_elevation_seconds = admin_elevation_seconds
        self._dummy_hash = dummy_hash or password_hasher.hash(DUMMY_HASH_INPUT)

    async def login(self, username: str, password: str) -> LoginResult:
        now = datetime.now(UTC)
        normalised = username.strip().lower()
        account = await self._repository.find_account(normalised)
        stored_hash = account.password_hash if account else self._dummy_hash
        password_valid = await to_thread.run_sync(
            self._hasher.verify,
            stored_hash,
            password,
        )
        locked = (
            account is not None
            and account.locked_until is not None
            and account.locked_until > now
        )
        if account is None or not password_valid or not account.is_active or locked:
            if account is not None and account.is_active and not locked:
                await self._record_failure(account, now)
            raise AuthenticationFailed()

        await self._repository.reset_failures(account)
        await self._repository.revoke_user_sessions(account)
        session_token = token_urlsafe(32)
        csrf_token = token_urlsafe(32)
        session = await self._repository.create_session(
            account,
            token_hash=hash_opaque_token(session_token),
            csrf_token_hash=hash_opaque_token(csrf_token),
            expires_at=now + timedelta(seconds=self._session_ttl),
        )
        return LoginResult(session, session_token, csrf_token)

    async def authenticate(self, session_token: str | None) -> SessionRecord:
        if not session_token:
            raise SessionRequired()
        session = await self._repository.find_session(
            hash_opaque_token(session_token),
            now=datetime.now(UTC),
            idle_cutoff=datetime.now(UTC) - timedelta(seconds=self._session_idle),
        )
        if session is None:
            await self._repository.commit_security_state()
            raise SessionRequired()
        return session

    async def logout(self, session: SessionRecord) -> None:
        await self._repository.revoke_session(session.id)

    async def refresh_csrf(self, session: SessionRecord) -> str:
        csrf_token = token_urlsafe(32)
        await self._repository.rotate_csrf(
            session.id,
            hash_opaque_token(csrf_token),
        )
        return csrf_token

    async def elevate(self, session: SessionRecord, password: str) -> datetime:
        if session.actor.role is not UserRole.PLATFORM_ADMIN:
            raise AdministrationAccessDenied()
        now = datetime.now(UTC)
        account = await self._repository.find_account(session.actor.username)
        if account is None or not account.is_active:
            raise AuthenticationFailed()
        valid = await to_thread.run_sync(
            self._hasher.verify,
            account.password_hash,
            password,
        )
        locked = account.locked_until is not None and account.locked_until > now
        if not valid or locked:
            if not locked:
                await self._record_failure(account, now)
            raise AuthenticationFailed()
        await self._repository.reset_failures(account)
        until = now + timedelta(seconds=self._admin_elevation_seconds)
        await self._repository.set_elevation(session.id, until)
        return until

    async def _record_failure(self, account: AccountRecord, now: datetime) -> None:
        await self._repository.record_failure(
            account,
            now=now,
            lockout_threshold=self._lockout_threshold,
            lockout_seconds=self._lockout_seconds,
        )
        await self._repository.commit_security_state()
