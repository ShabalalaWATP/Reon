"""Password and opaque-session authentication use cases."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from anyio import to_thread

from istari_service.auth_ports import AuthRepository as AuthRepository
from istari_service.auth_primitives import (
    DUMMY_HASH_INPUT as DUMMY_HASH_INPUT,
)
from istari_service.auth_primitives import (
    PasswordHasher as PasswordHasher,
)
from istari_service.auth_primitives import (
    csrf_token_for_session as csrf_token_for_session,
)
from istari_service.auth_primitives import (
    hash_opaque_token as hash_opaque_token,
)
from istari_service.compliance_models import SecurityOutcome
from istari_service.domain import AccountRecord, SessionRecord
from istari_service.errors import (
    AdministrationAccessDenied,
    AuthenticationFailed,
    AuthenticationRateLimited,
    AuthenticationUnavailable,
    SessionRequired,
)
from istari_service.login_rate_limiter import (
    LoginAttemptLimiter,
    LoginRateLimitPolicy,
    LoginRateLimitUnavailable,
    credential_budget_key,
)
from istari_service.models import UserRole
from istari_service.security_events import SecurityEventCommand, SecurityEventRecorder


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
        login_limiter: LoginAttemptLimiter | None = None,
        login_rate_limit_policy: LoginRateLimitPolicy | None = None,
        password_semaphore: asyncio.Semaphore | None = None,
        security_events: SecurityEventRecorder | None = None,
        pseudonym_key: bytes | None = None,
    ) -> None:
        self._repository = repository
        self._hasher = password_hasher
        self._session_ttl = session_ttl_seconds
        self._session_idle = session_idle_seconds
        self._lockout_threshold = lockout_threshold
        self._lockout_seconds = lockout_seconds
        self._admin_elevation_seconds = admin_elevation_seconds
        self._dummy_hash = dummy_hash or password_hasher.hash(DUMMY_HASH_INPUT)
        self._login_limiter = login_limiter
        self._login_rate_limit_policy = login_rate_limit_policy
        self._password_semaphore = password_semaphore
        self._security_events = security_events
        self._pseudonym_key = pseudonym_key
        if login_limiter is not None and pseudonym_key is None:
            raise ValueError("login limiter requires a pseudonym key")

    async def login(
        self,
        username: str,
        password: str,
        *,
        source_key: str = "source:unit-test",
    ) -> LoginResult:
        now = datetime.now(UTC)
        if self._login_limiter is not None:
            if self._login_rate_limit_policy is None:
                raise RuntimeError("login rate-limit policy is required")
            try:
                decision = await self._login_limiter.consume(
                    source_key,
                    self._login_rate_limit_policy,
                )
            except LoginRateLimitUnavailable as error:
                raise AuthenticationUnavailable() from error
            if not decision.allowed:
                if decision.first_denial:
                    await self._record_security(
                        "LOGIN_RATE_LIMIT",
                        SecurityOutcome.RATE_LIMITED,
                        "ADMISSION_BUDGET",
                        source=source_key,
                    )
                raise AuthenticationRateLimited(decision.retry_after_seconds)
        normalised = username.strip().lower()
        account = await self._repository.find_account(normalised)
        stored_hash = account.password_hash if account else self._dummy_hash
        password_valid = await self._verify_password(stored_hash, password)
        if account is None or not password_valid or not account.is_active:
            credential_decision = None
            if self._login_limiter is not None:
                if self._pseudonym_key is None:  # pragma: no cover - constructor guard
                    raise RuntimeError("login pseudonym key is unavailable")
                credential_decision = await self._login_limiter.consume_scope_only(
                    credential_budget_key(
                        normalised,
                        pseudonym_key=self._pseudonym_key,
                    ),
                    self._login_rate_limit_policy,  # type: ignore[arg-type]
                )
            if account is not None and account.is_active:
                await self._record_failure(account, now)
            await self._record_security(
                "LOGIN",
                SecurityOutcome.FAILURE,
                "INVALID_CREDENTIALS",
                subject=normalised,
                source=source_key,
            )
            if credential_decision is not None and not credential_decision.allowed:
                raise AuthenticationRateLimited(credential_decision.retry_after_seconds)
            raise AuthenticationFailed()

        await self._repository.reset_failures(account)
        await self._repository.revoke_user_sessions(account)
        session_token = token_urlsafe(32)
        csrf_token = csrf_token_for_session(session_token)
        session = await self._repository.create_session(
            account,
            token_hash=hash_opaque_token(session_token),
            csrf_token_hash=hash_opaque_token(csrf_token),
            expires_at=now + timedelta(seconds=self._session_ttl),
        )
        await self._record_security(
            "LOGIN",
            SecurityOutcome.SUCCESS,
            "AUTHENTICATED",
            actor_user_id=account.actor.id,
            subject=normalised,
            source=source_key,
        )
        return LoginResult(session, session_token, csrf_token)

    async def authenticate(
        self, session_token: str | None, *, record_activity: bool = False
    ) -> SessionRecord:
        if not session_token:
            raise SessionRequired()
        session = await self._repository.find_session(
            hash_opaque_token(session_token),
            now=datetime.now(UTC),
            idle_cutoff=datetime.now(UTC) - timedelta(seconds=self._session_idle),
            touch=record_activity,
        )
        if session is None:
            await self._repository.commit_security_state()
            raise SessionRequired()
        return session

    async def logout(self, session: SessionRecord) -> None:
        await self._repository.revoke_session(session.id)

    async def record_activity(self, session: SessionRecord) -> None:
        await self._repository.touch_session(session.id, now=datetime.now(UTC))

    async def elevate(self, session: SessionRecord, password: str) -> datetime:
        if session.actor.role is not UserRole.PLATFORM_ADMIN:
            await self._record_security(
                "STEP_UP",
                SecurityOutcome.FAILURE,
                "ROLE_DENIED",
                actor_user_id=session.actor.id,
            )
            raise AdministrationAccessDenied()
        now = datetime.now(UTC)
        account = await self._repository.find_account(session.actor.username)
        if account is None or not account.is_active:
            await self._record_security(
                "STEP_UP",
                SecurityOutcome.FAILURE,
                "ACCOUNT_UNAVAILABLE",
                actor_user_id=session.actor.id,
            )
            raise AuthenticationFailed()
        valid = await self._verify_password(account.password_hash, password)
        locked = account.locked_until is not None and account.locked_until > now
        if not valid or locked:
            if locked:
                await self._record_security(
                    "STEP_UP",
                    SecurityOutcome.FAILURE,
                    "ACCOUNT_LOCKED",
                    actor_user_id=session.actor.id,
                )
                raise AuthenticationFailed()
            await self._record_failure(account, now)
            await self._record_security(
                "STEP_UP",
                SecurityOutcome.FAILURE,
                "INVALID_CREDENTIALS",
                actor_user_id=session.actor.id,
            )
            raise AuthenticationFailed()
        await self._repository.reset_failures(account)
        until = now + timedelta(seconds=self._admin_elevation_seconds)
        await self._repository.set_elevation(session.id, until)
        await self._record_security(
            "STEP_UP",
            SecurityOutcome.SUCCESS,
            "ELEVATED",
            actor_user_id=session.actor.id,
        )
        return until

    async def _record_security(
        self,
        event_type: str,
        outcome: SecurityOutcome,
        reason_code: str,
        *,
        actor_user_id: UUID | None = None,
        subject: str | None = None,
        source: str | None = None,
    ) -> None:
        if self._security_events is None:
            return
        await self._security_events.record(
            SecurityEventCommand(
                event_type,
                outcome,
                reason_code,
                actor_user_id=actor_user_id,
                subject=subject,
                source=source,
            )
        )

    async def _record_failure(self, account: AccountRecord, now: datetime) -> None:
        await self._repository.record_failure(
            account,
            now=now,
            lockout_threshold=self._lockout_threshold,
            lockout_seconds=self._lockout_seconds,
        )
        await self._repository.commit_security_state()

    async def _verify_password(self, stored_hash: str, password: str) -> bool:
        if self._password_semaphore is None:
            return await to_thread.run_sync(self._hasher.verify, stored_hash, password)
        async with self._password_semaphore:
            return await to_thread.run_sync(self._hasher.verify, stored_hash, password)
