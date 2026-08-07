"""FastAPI composition dependencies at the HTTP boundary."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.auth_service import AuthService, PasswordHasher
from istari_service.config import Settings
from istari_service.domain import Actor, SessionRecord
from istari_service.errors import AdministrationAccessDenied, StepUpRequired
from istari_service.models import UserRole
from istari_service.repositories.auth import SqlAlchemyAuthRepository
from istari_service.security import require_csrf
from istari_service.team_membership_sync import synchronise_due_team_memberships
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
            if await synchronise_due_team_memberships(session):
                await session.commit()
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


def auth_service(request: Request, session: DatabaseSession) -> AuthService:
    hasher = cast(PasswordHasher, request.app.state.password_hasher)
    dummy_hash = cast(str, request.app.state.dummy_password_hash)
    settings = settings_from_request(request)
    return AuthService(
        SqlAlchemyAuthRepository(session),
        hasher,
        session_ttl_seconds=settings.session_ttl_seconds,
        session_idle_seconds=settings.session_idle_seconds,
        admin_elevation_seconds=settings.admin_elevation_seconds,
        dummy_hash=dummy_hash,
    )


AuthDependency = Annotated[AuthService, Depends(auth_service)]


async def current_session(
    request: Request,
    service: AuthDependency,
) -> SessionRecord:
    settings = settings_from_request(request)
    return await service.authenticate(request.cookies.get(settings.session_cookie_name))


CurrentSession = Annotated[SessionRecord, Depends(current_session)]


async def mutation_session(
    request: Request,
    session: CurrentSession,
) -> SessionRecord:
    settings = settings_from_request(request)
    require_csrf(
        session,
        request.headers.get("X-CSRF-Token"),
        request.headers.get("Origin"),
        settings.trusted_origins,
    )
    return session


MutationSession = Annotated[SessionRecord, Depends(mutation_session)]


def actor_from_session(session: CurrentSession) -> Actor:
    return session.actor


def mutation_actor(session: MutationSession) -> Actor:
    return session.actor


CurrentActor = Annotated[Actor, Depends(actor_from_session)]
MutationActor = Annotated[Actor, Depends(mutation_actor)]


def elevated_mutation_actor(session: MutationSession) -> Actor:
    if session.actor.role is not UserRole.PLATFORM_ADMIN:
        raise AdministrationAccessDenied()
    elevated_until = session.elevated_until
    if elevated_until is None:
        raise StepUpRequired()
    if elevated_until.tzinfo is None:
        elevated_until = elevated_until.replace(tzinfo=UTC)
    if elevated_until <= datetime.now(UTC):
        raise StepUpRequired()
    return session.actor


ElevatedMutationActor = Annotated[Actor, Depends(elevated_mutation_actor)]
