"""Shared PostgreSQL transaction lock for legal hold and disposal ordering."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

RETENTION_LOCK_KEY = 4_981_472_921


async def acquire_retention_lock(session: AsyncSession) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(select(func.pg_advisory_xact_lock(RETENTION_LOCK_KEY)))
