"""Disposable PostgreSQL database lifecycle for destructive migration assurance."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


async def create_assurance_databases(
    admin_url: str,
) -> tuple[str, str, tuple[str, str]]:
    """Create isolated populated and empty-path databases from a CI admin URL."""

    parsed = make_url(admin_url)
    if parsed.drivername != "postgresql+asyncpg":
        raise ValueError("migration assurance requires a PostgreSQL asyncpg URL")
    names = (
        f"mist_migration_{uuid4().hex}",
        f"mist_empty_{uuid4().hex}",
    )
    maintenance_url = parsed.set(database="postgres").render_as_string(
        hide_password=False
    )
    engine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    created: list[str] = []
    try:
        async with engine.connect() as connection:
            for name in names:
                await connection.execute(
                    text(f'CREATE DATABASE "{name}" TEMPLATE template0')
                )
                created.append(name)
    except BaseException:
        async with engine.connect() as connection:
            for name in created:
                await connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                )
        raise
    finally:
        await engine.dispose()
    urls = tuple(
        parsed.set(database=name).render_as_string(hide_password=False)
        for name in names
    )
    return urls[0], urls[1], names


async def drop_assurance_databases(
    admin_url: str, database_names: tuple[str, str]
) -> None:
    """Force-remove both uniquely named CI databases even after failed assertions."""

    parsed = make_url(admin_url)
    maintenance_url = parsed.set(database="postgres").render_as_string(
        hide_password=False
    )
    engine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            for name in database_names:
                await connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                )
    finally:
        await engine.dispose()
