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
    "request_conversation_messages",
    "request_conversations",
    "request_events",
    "security_events",
    "team_activity_events",
    "work_package_activity",
)
NON_DELETABLE_TABLES = (
    "approved_workflow_definitions",
    "configuration_versions",
    "request_conversation_deliveries",
)


def _role(name: str, value: str | None) -> str:
    if value is None or ROLE_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lower-case PostgreSQL role name")
    return f'"{value}"'


def permission_statements(
    runtime_role: str,
    backup_role: str,
    maintenance_role: str | None = None,
) -> tuple[str, ...]:
    """Return the reviewed grant set for schema-created application objects."""

    runtime = _role("APP_RUNTIME_DATABASE_USER", runtime_role)
    backup = _role("APP_BACKUP_DATABASE_USER", backup_role)
    immutable = ", ".join(f'public."{table}"' for table in IMMUTABLE_TABLES)
    non_deletable = ", ".join(f'public."{table}"' for table in NON_DELETABLE_TABLES)
    statements = (
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"GRANT USAGE ON SCHEMA public TO {runtime}, {backup}",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        f"TO {runtime}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {runtime}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {backup}",
        f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {backup}",
        f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {immutable} FROM {runtime}",
        f"REVOKE DELETE, TRUNCATE ON TABLE {non_deletable} FROM {runtime}",
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE public.legal_holds "
        f"FROM {runtime}",
    )
    if maintenance_role is None:
        return statements
    maintenance = _role("APP_MAINTENANCE_DATABASE_USER", maintenance_role)
    deletable = ", ".join(
        f"public.{table}"
        for table in (
            "account_requests",
            "action_projections",
            "clarification_threads",
            "feedback",
            "notification_events",
            "notification_recipients",
            "product_access_events",
            "request_drafts",
            "security_events",
            "sessions",
            "team_activity_events",
            "work_package_activity",
            "workflow_outbox",
        )
    )
    return (
        *statements,
        f"GRANT USAGE ON SCHEMA public TO {maintenance}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {maintenance}",
        f"GRANT INSERT ON TABLE public.legal_holds TO {maintenance}",
        f"GRANT UPDATE (released_at, released_by) ON TABLE public.legal_holds "
        f"TO {maintenance}",
        f"GRANT INSERT ON TABLE public.operational_runs TO {maintenance}",
        "GRANT UPDATE (username, email, display_name, password_hash, scope, "
        "profile_team, rank_or_grade, service_number, additional_information, "
        "skills, assistance_email_hash, assistance_email_key_id, updated_at) "
        f"ON TABLE public.users TO {maintenance}",
        f"GRANT DELETE ON TABLE {deletable} TO {maintenance}",
    )


async def apply_permissions() -> None:
    """Apply grants with the migration owner, then dispose the credential."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must be an async PostgreSQL migration URL")
    statements = permission_statements(
        os.getenv("APP_RUNTIME_DATABASE_USER", ""),
        os.getenv("APP_BACKUP_DATABASE_USER", ""),
        os.getenv("APP_MAINTENANCE_DATABASE_USER") or None,
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
