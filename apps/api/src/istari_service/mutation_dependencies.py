"""FastAPI CSRF, context-fencing and privileged actor dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from istari_service.authentication_dependencies import (
    CurrentSession,
    DetachedCurrentSession,
    _security_event_recorder,
)
from istari_service.compliance_models import SecurityOutcome
from istari_service.database_dependencies import DatabaseSession, settings_from_request
from istari_service.domain import Actor, SessionRecord
from istari_service.errors import (
    AdministrationAccessDenied,
    CsrfFailed,
    ObjectNotFound,
    SessionRequired,
    StepUpRequired,
)
from istari_service.models import UserRole
from istari_service.repositories.auth import SqlAlchemyAuthRepository
from istari_service.security import require_csrf
from istari_service.security_events import SecurityEventCommand


async def _record_csrf_denial(request: Request, actor_id: object) -> None:
    await _security_event_recorder(request).record(
        SecurityEventCommand(
            "CSRF_DENIAL",
            SecurityOutcome.FAILURE,
            "CSRF_VALIDATION_FAILED",
            actor_user_id=actor_id,  # type: ignore[arg-type]
        )
    )


def _require_request_csrf(
    request: Request,
    session: SessionRecord,
) -> None:
    settings = settings_from_request(request)
    require_csrf(
        session,
        request.headers.get("X-CSRF-Token"),
        request.headers.get("Origin"),
        settings.trusted_origins,
    )


async def mutation_session(
    request: Request,
    session: CurrentSession,
    database: DatabaseSession,
) -> SessionRecord:
    try:
        _require_request_csrf(request, session)
    except CsrfFailed:
        await _record_csrf_denial(request, session.actor.id)
        raise
    locked = await SqlAlchemyAuthRepository(database).lock_mutation_context(
        session.id, expected_context_version=session.context_version
    )
    if not locked:
        raise SessionRequired()
    return session


MutationSession = Annotated[SessionRecord, Depends(mutation_session)]


def mutation_actor(session: MutationSession) -> Actor:
    return session.actor


MutationActor = Annotated[Actor, Depends(mutation_actor)]


def staff_actor_from_session(session: CurrentSession) -> Actor:
    if session.actor.role is UserRole.REQUESTER:
        raise ObjectNotFound()
    return session.actor


def staff_mutation_actor(session: MutationSession) -> Actor:
    if session.actor.role is UserRole.REQUESTER:
        raise ObjectNotFound()
    return session.actor


StaffActor = Annotated[Actor, Depends(staff_actor_from_session)]
StaffMutationActor = Annotated[Actor, Depends(staff_mutation_actor)]


async def detached_mutation_session(
    request: Request,
    session: DetachedCurrentSession,
) -> SessionRecord:
    try:
        _require_request_csrf(request, session)
    except CsrfFailed:
        await _record_csrf_denial(request, session.actor.id)
        raise
    return session


DetachedMutationSession = Annotated[
    SessionRecord,
    Depends(detached_mutation_session),
]


def detached_mutation_actor(session: DetachedMutationSession) -> Actor:
    return session.actor


DetachedMutationActor = Annotated[
    Actor,
    Depends(detached_mutation_actor),
]


async def elevated_mutation_actor(request: Request, session: MutationSession) -> Actor:
    if session.actor.role is not UserRole.PLATFORM_ADMIN:
        await _security_event_recorder(request).record(
            SecurityEventCommand(
                "ROLE_DENIAL",
                SecurityOutcome.FAILURE,
                "PLATFORM_ADMIN_REQUIRED",
                actor_user_id=session.actor.id,
            )
        )
        raise AdministrationAccessDenied()
    elevated_until = session.elevated_until
    if elevated_until is None:
        await _record_step_up_expired(request, session)
        raise StepUpRequired()
    if elevated_until.tzinfo is None:
        elevated_until = elevated_until.replace(tzinfo=UTC)
    if elevated_until <= datetime.now(UTC):
        await _record_step_up_expired(request, session)
        raise StepUpRequired()
    return session.actor


async def _record_step_up_expired(request: Request, session: SessionRecord) -> None:
    await _security_event_recorder(request).record(
        SecurityEventCommand(
            "STEP_UP",
            SecurityOutcome.EXPIRED,
            "ELEVATION_REQUIRED",
            actor_user_id=session.actor.id,
        )
    )


ElevatedMutationActor = Annotated[Actor, Depends(elevated_mutation_actor)]
