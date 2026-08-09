"""Apply least-privilege PostgreSQL grants after schema migration."""

from __future__ import annotations

import asyncio
import os
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
IMMUTABLE_TABLES = (
    "admin_audit_events",
    "analytics_export_audit_events",
    "configuration_activations",
    "configuration_approvals",
    "feedback",
    "operational_analytics_facts",
    "operational_runs",
    "product_access_events",
    "request_configuration_pins",
    "request_events",
    "team_activity_events",
    "work_package_activity",
)
NON_DELETABLE_TABLES = (
    "approved_workflow_definitions",
    "configuration_versions",
)


def _role(name: str, value: str | None) -> str:
    if value is None or ROLE_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lower-case PostgreSQL role name")
    return f'"{value}"'


def permission_statements(runtime_role: str, backup_role: str) -> tuple[str, ...]:
    """Return the reviewed grant set for schema-created application objects."""

    runtime = _role("APP_RUNTIME_DATABASE_USER", runtime_role)
    backup = _role("APP_BACKUP_DATABASE_USER", backup_role)
    immutable = ", ".join(f'public."{table}"' for table in IMMUTABLE_TABLES)
    non_deletable = ", ".join(f'public."{table}"' for table in NON_DELETABLE_TABLES)
    return (
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"GRANT USAGE ON SCHEMA public TO {runtime}, {backup}",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        f"TO {runtime}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {runtime}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {backup}",
        f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {backup}",
        f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {immutable} FROM {runtime}",
        f"REVOKE DELETE, TRUNCATE ON TABLE {non_deletable} FROM {runtime}",
    )


async def apply_permissions() -> None:
    """Apply grants with the migration owner, then dispose the credential."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must be an async PostgreSQL migration URL")
    statements = permission_statements(
        os.getenv("APP_RUNTIME_DATABASE_USER", ""),
        os.getenv("APP_BACKUP_DATABASE_USER", ""),
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            if connection.dialect.name != "postgresql":
                raise ValueError("database privilege controls require PostgreSQL")
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def main() -> None:
    """Command entry point used only by the one-shot migration container."""

    asyncio.run(apply_permissions())


if __name__ == "__main__":
    main()
