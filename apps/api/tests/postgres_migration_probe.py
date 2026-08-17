"""Small PostgreSQL assertion helpers shared by migration assurance phases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

REVISION_0043 = "0043_security_event_dedup"
REVISION_0044 = "0044_context_conversations"
REVISION_0045 = "0045_notification_contexts"
REVISION_0046 = "0046_product_package_policy"
REVISION_0047 = "0047_action_view_contexts"
REVISION_0048 = "0048_notification_position"
REVISION_0049 = "0049_legacy_product_cleanup"


async def assert_revision(connection: AsyncConnection, revision: str) -> None:
    assert (
        await scalar(connection, "SELECT version_num FROM alembic_version") == revision
    )


async def column_exists(
    connection: AsyncConnection, table_name: str, column_name: str
) -> bool:
    return bool(
        await scalar(
            connection,
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:table "
            "AND column_name=:column)",
            {"table": table_name, "column": column_name},
        )
    )


async def scalar(
    connection: AsyncConnection,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> Any:
    return await connection.scalar(text(statement), parameters or {})


async def rows(
    connection: AsyncConnection,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> list[tuple[Any, ...]]:
    result = await connection.execute(text(statement), parameters or {})
    return [tuple(row) for row in result]


async def must_reject(
    connection: AsyncConnection,
    statement: str,
    parameters: Mapping[str, Any],
) -> None:
    savepoint = await connection.begin_nested()
    try:
        await connection.execute(text(statement), parameters)
    except DBAPIError:
        await savepoint.rollback()
    else:
        await savepoint.rollback()
        raise AssertionError(f"PostgreSQL accepted invalid migration data: {statement}")
