"""Secure browser-session context switching use case."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Protocol
from uuid import UUID

from istari_service.auth_service import csrf_token_for_session, hash_opaque_token
from istari_service.compliance_models import SecurityEvent, SecurityOutcome
from istari_service.domain import SessionRecord
from istari_service.errors import IdentityContextDenied
from istari_service.models import IdentityContext
from istari_service.security_events import SecurityEventCommand, SecurityEventRecorder


class IdentityContextRepository(Protocol):
    async def switch_context(
        self,
        session_id: UUID,
        *,
        context: IdentityContext,
        expected_context_version: int,
        token_hash: str,
        csrf_token_hash: str,
    ) -> SessionRecord: ...

    async def commit_security_state(
        self, security_event: SecurityEvent | None = None
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ContextSwitchResult:
    session: SessionRecord
    session_token: str
    csrf_token: str


class IdentityContextService:
    def __init__(
        self,
        repository: IdentityContextRepository,
        security_events: SecurityEventRecorder,
    ) -> None:
        self._repository = repository
        self._security_events = security_events

    async def switch(
        self,
        session: SessionRecord,
        context: IdentityContext,
    ) -> ContextSwitchResult:
        """Rotate all browser session secrets while changing effective authority."""

        session_token = token_urlsafe(32)
        csrf_token = csrf_token_for_session(session_token)
        try:
            switched = await self._repository.switch_context(
                session.id,
                context=context,
                expected_context_version=session.context_version,
                token_hash=hash_opaque_token(session_token),
                csrf_token_hash=hash_opaque_token(csrf_token),
            )
        except PermissionError as error:
            await self._record(
                session,
                context,
                SecurityOutcome.FAILURE,
                "CONTEXT_NOT_ENTITLED",
            )
            raise IdentityContextDenied() from error
        event = self._security_events.build(
            self._command(
                session,
                context,
                SecurityOutcome.SUCCESS,
                "CONTEXT_SWITCHED",
            )
        )
        await self._repository.commit_security_state(event)
        return ContextSwitchResult(switched, session_token, csrf_token)

    async def _record(
        self,
        session: SessionRecord,
        context: IdentityContext,
        outcome: SecurityOutcome,
        reason: str,
    ) -> None:
        await self._security_events.record(
            self._command(session, context, outcome, reason)
        )

    @staticmethod
    def _command(
        session: SessionRecord,
        context: IdentityContext,
        outcome: SecurityOutcome,
        reason: str,
    ) -> SecurityEventCommand:
        return SecurityEventCommand(
            "IDENTITY_CONTEXT_SWITCH",
            outcome,
            reason,
            actor_user_id=session.actor.id,
            subject=f"{session.active_context.value}:{context.value}",
        )
