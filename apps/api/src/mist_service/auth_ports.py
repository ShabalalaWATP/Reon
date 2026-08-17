"""Persistence-independent authentication repository contract."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.domain import AccountRecord, SessionRecord


class AuthRepository(Protocol):
    async def find_account(self, username: str) -> AccountRecord | None: ...

    async def record_step_up_failure(
        self,
        account: AccountRecord,
        *,
        now: datetime,
        lockout_threshold: int,
        lockout_seconds: int,
    ) -> None:
        """Count an authenticated step-up failure and lock at the threshold.

        Public authentication must never reach this contract. Unauthenticated
        callers are throttled by source and credential budgets instead, so that
        a named account cannot be hard-locked by someone who only knows a
        username.
        """
        ...

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
        touch: bool = False,
    ) -> SessionRecord | None: ...

    async def touch_session(self, session_id: UUID, *, now: datetime) -> None: ...

    async def revoke_session(self, session_id: UUID) -> None: ...

    async def rotate_csrf(self, session_id: UUID, csrf_token_hash: str) -> None: ...

    async def set_elevation(
        self,
        session_id: UUID,
        until: datetime,
        *,
        token_hash: str,
        csrf_token_hash: str,
    ) -> None: ...

    async def commit_security_state(self) -> None: ...
