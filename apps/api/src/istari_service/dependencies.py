"""FastAPI composition dependencies at the HTTP boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.audit import AUDIT_KEY_INFO
from istari_service.auth_service import AuthService, PasswordHasher
from istari_service.compliance_models import SecurityOutcome
from istari_service.config import Settings
from istari_service.database import SECURITY_PSEUDONYM_KEY_INFO
from istari_service.domain import Actor, SessionRecord
from istari_service.errors import AdministrationAccessDenied, CsrfFailed, StepUpRequired
from istari_service.login_rate_limiter import LoginRateLimitPolicy
from istari_service.models import UserRole
from istari_service.repositories.auth import SqlAlchemyAuthRepository
from istari_service.repositories.login_rate_limits import (
    SqlAlchemyLoginAttemptLimiter,
)
from istari_service.security import require_csrf
from istari_service.security_events import SecurityEventCommand, SecurityEventRecorder
from istari_service.workflow.engine import WorkflowEngine


def settings_from_request(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def workflow_from_request(request: Request) -> WorkflowEngine:
    return cast(WorkflowEngine, request.app.state.workflow_engine)


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


async def readiness_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a raw read-only session so readiness can report database failure."""

    factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )
    async with factory() as session:
        yield session


ReadinessDatabaseSession = Annotated[
    AsyncSession,
    Depends(readiness_database_session),
]
AppSettings = Annotated[Settings, Depends(settings_from_request)]
WorkflowDependency = Annotated[WorkflowEngine, Depends(workflow_from_request)]


def session_factory_from_request(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    return cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )


SessionFactoryDependency = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(session_factory_from_request),
]


def login_pseudonym_key_from_request(request: Request) -> bytes:
    factory = session_factory_from_request(request)
    return cast(bytes, factory.kw["info"][SECURITY_PSEUDONYM_KEY_INFO])


LoginPseudonymKey = Annotated[bytes, Depends(login_pseudonym_key_from_request)]


def _auth_service_for_session(request: Request, session: AsyncSession) -> AuthService:
    hasher = cast(PasswordHasher, request.app.state.password_hasher)
    dummy_hash = cast(str, request.app.state.dummy_password_hash)
    settings = settings_from_request(request)
    password_semaphore = cast(
        asyncio.Semaphore,
        request.app.state.login_password_semaphore,
    )
    return AuthService(
        SqlAlchemyAuthRepository(session),
        hasher,
        session_ttl_seconds=settings.session_ttl_seconds,
        session_idle_seconds=settings.session_idle_seconds,
        admin_elevation_seconds=settings.admin_elevation_seconds,
        dummy_hash=dummy_hash,
        login_limiter=SqlAlchemyLoginAttemptLimiter(
            session_factory_from_request(request),
            timeout_seconds=settings.login_rate_limit_timeout_seconds,
        ),
        login_rate_limit_policy=LoginRateLimitPolicy(
            window_seconds=settings.login_rate_limit_window_seconds,
            per_source=settings.login_rate_limit_per_source,
            global_limit=settings.login_rate_limit_global,
        ),
        password_semaphore=password_semaphore,
        security_events=_security_event_recorder(request),
        pseudonym_key=login_pseudonym_key_from_request(request),
    )


def _security_event_recorder(request: Request) -> SecurityEventRecorder:
    factory = session_factory_from_request(request)
    return SecurityEventRecorder(
        factory,
        pseudonym_key=cast(bytes, factory.kw["info"][AUDIT_KEY_INFO]),
    )


def auth_service(request: Request, session: DatabaseSession) -> AuthService:
    return _auth_service_for_session(request, session)


AuthDependency = Annotated[AuthService, Depends(auth_service)]


async def current_session(
    request: Request,
    service: AuthDependency,
) -> SessionRecord:
    settings = settings_from_request(request)
    session = await service.authenticate(
        request.cookies.get(settings.session_cookie_name)
    )
    request.state.authenticated_actor = session.actor
    return session


CurrentSession = Annotated[SessionRecord, Depends(current_session)]


async def mutation_session(
    request: Request,
    session: CurrentSession,
) -> SessionRecord:
    settings = settings_from_request(request)
    try:
        require_csrf(
            session,
            request.headers.get("X-CSRF-Token"),
            request.headers.get("Origin"),
            settings.trusted_origins,
        )
    except CsrfFailed:
        await _security_event_recorder(request).record(
            SecurityEventCommand(
                "CSRF_DENIAL",
                SecurityOutcome.FAILURE,
                "CSRF_VALIDATION_FAILED",
                actor_user_id=session.actor.id,
            )
        )
        raise
    return session


MutationSession = Annotated[SessionRecord, Depends(mutation_session)]


def actor_from_session(session: CurrentSession) -> Actor:
    return session.actor


def mutation_actor(session: MutationSession) -> Actor:
    return session.actor


CurrentActor = Annotated[Actor, Depends(actor_from_session)]
MutationActor = Annotated[Actor, Depends(mutation_actor)]


async def detached_current_session(request: Request) -> SessionRecord:
    """Authenticate and close the database session before response streaming."""

    factory = session_factory_from_request(request)
    async with factory() as session:
        try:
            service = _auth_service_for_session(request, session)
            settings = settings_from_request(request)
            record = await service.authenticate(
                request.cookies.get(settings.session_cookie_name)
            )
            request.state.authenticated_actor = record.actor
            await session.commit()
            return record
        except BaseException:
            await session.rollback()
            raise


DetachedCurrentSession = Annotated[
    SessionRecord,
    Depends(detached_current_session),
]


def detached_actor_from_session(session: DetachedCurrentSession) -> Actor:
    return session.actor


DetachedCurrentActor = Annotated[
    Actor,
    Depends(detached_actor_from_session),
]


async def detached_mutation_actor(
    request: Request,
    session: DetachedCurrentSession,
) -> Actor:
    settings = settings_from_request(request)
    try:
        require_csrf(
            session,
            request.headers.get("X-CSRF-Token"),
            request.headers.get("Origin"),
            settings.trusted_origins,
        )
    except CsrfFailed:
        await _security_event_recorder(request).record(
            SecurityEventCommand(
                "CSRF_DENIAL",
                SecurityOutcome.FAILURE,
                "CSRF_VALIDATION_FAILED",
                actor_user_id=session.actor.id,
            )
        )
        raise
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
