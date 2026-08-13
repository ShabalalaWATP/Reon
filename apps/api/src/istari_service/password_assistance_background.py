"""Deferred password-assistance processing outside the public transaction."""

from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.repositories.platform_security import (
    SqlAlchemyPlatformSecurityRepository,
)
from istari_service.services.platform_security_service import PlatformSecurityService


async def process_password_assistance(
    sessions: async_sessionmaker[AsyncSession], attempt_id: UUID, email: str
) -> None:
    async with sessions() as session, session.begin():
        service = PlatformSecurityService(SqlAlchemyPlatformSecurityRepository(session))
        await service.process_password_assistance(attempt_id, email)


def schedule_password_assistance(
    background: BackgroundTasks,
    sessions: async_sessionmaker[AsyncSession],
    attempt_id: UUID | None,
    email: str,
) -> None:
    if attempt_id is not None:
        background.add_task(process_password_assistance, sessions, attempt_id, email)
