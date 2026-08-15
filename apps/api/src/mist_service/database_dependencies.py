"""FastAPI settings, workflow and database-session dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.config import Settings
from mist_service.database import SECURITY_PSEUDONYM_KEY_INFO
from mist_service.workflow.engine import WorkflowEngine


def settings_from_request(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def workflow_from_request(request: Request) -> WorkflowEngine:
    return cast(WorkflowEngine, request.app.state.workflow_engine)


def session_factory_from_request(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    return cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = session_factory_from_request(request)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def readiness_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a raw read-only session so readiness can report database failure."""

    async with session_factory_from_request(request)() as session:
        yield session


def login_pseudonym_key_from_request(request: Request) -> bytes:
    factory = session_factory_from_request(request)
    return cast(bytes, factory.kw["info"][SECURITY_PSEUDONYM_KEY_INFO])


DatabaseSession = Annotated[AsyncSession, Depends(database_session)]
ReadinessDatabaseSession = Annotated[
    AsyncSession,
    Depends(readiness_database_session),
]
AppSettings = Annotated[Settings, Depends(settings_from_request)]
WorkflowDependency = Annotated[WorkflowEngine, Depends(workflow_from_request)]
SessionFactoryDependency = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(session_factory_from_request),
]
LoginPseudonymKey = Annotated[bytes, Depends(login_pseudonym_key_from_request)]
