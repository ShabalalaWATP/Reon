"""FastAPI authentication service and current-session dependencies."""

from __future__ import annotations

import asyncio
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.audit import AUDIT_KEY_INFO
from mist_service.auth_service import AuthService, PasswordHasher
from mist_service.database_dependencies import (
    DatabaseSession,
    login_pseudonym_key_from_request,
    session_factory_from_request,
    settings_from_request,
)
from mist_service.domain import Actor, SessionRecord
from mist_service.identity_context_service import IdentityContextService
from mist_service.login_rate_limiter import LoginRateLimitPolicy
from mist_service.repositories.auth import SqlAlchemyAuthRepository
from mist_service.repositories.login_rate_limits import (
    SqlAlchemyLoginAttemptLimiter,
)
from mist_service.security_events import SecurityEventRecorder


def _security_event_recorder(request: Request) -> SecurityEventRecorder:
    factory = session_factory_from_request(request)
    return SecurityEventRecorder(
        factory,
        pseudonym_key=cast(bytes, factory.kw["info"][AUDIT_KEY_INFO]),
    )


def _auth_service_for_session(request: Request, session: AsyncSession) -> AuthService:
    settings = settings_from_request(request)
    return AuthService(
        SqlAlchemyAuthRepository(session),
        cast(PasswordHasher, request.app.state.password_hasher),
        session_ttl_seconds=settings.session_ttl_seconds,
        session_idle_seconds=settings.session_idle_seconds,
        admin_elevation_seconds=settings.admin_elevation_seconds,
        dummy_hash=cast(str, request.app.state.dummy_password_hash),
        login_limiter=SqlAlchemyLoginAttemptLimiter(
            session_factory_from_request(request),
            timeout_seconds=settings.login_rate_limit_timeout_seconds,
        ),
        login_rate_limit_policy=LoginRateLimitPolicy(
            window_seconds=settings.login_rate_limit_window_seconds,
            per_source=settings.login_rate_limit_per_source,
            global_limit=settings.login_rate_limit_global,
        ),
        password_semaphore=cast(
            asyncio.Semaphore,
            request.app.state.login_password_semaphore,
        ),
        security_events=_security_event_recorder(request),
        pseudonym_key=login_pseudonym_key_from_request(request),
    )


def auth_service(request: Request, session: DatabaseSession) -> AuthService:
    return _auth_service_for_session(request, session)


AuthDependency = Annotated[AuthService, Depends(auth_service)]


def identity_context_service(
    request: Request, session: DatabaseSession
) -> IdentityContextService:
    return IdentityContextService(
        SqlAlchemyAuthRepository(session),
        _security_event_recorder(request),
    )


IdentityContextDependency = Annotated[
    IdentityContextService,
    Depends(identity_context_service),
]


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


def actor_from_session(session: CurrentSession) -> Actor:
    return session.actor


CurrentActor = Annotated[Actor, Depends(actor_from_session)]


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


DetachedCurrentSession = Annotated[SessionRecord, Depends(detached_current_session)]


def detached_actor_from_session(session: DetachedCurrentSession) -> Actor:
    return session.actor


DetachedCurrentActor = Annotated[
    Actor,
    Depends(detached_actor_from_session),
]
