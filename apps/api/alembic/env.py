from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import JSON, Connection, Enum, pool
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.elements import conv

from istari_service.model_registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

enum_check_logical_names = frozenset(
    f"ck_{table.name}_{column.type.name}"
    for table in target_metadata.tables.values()
    for column in table.columns
    if isinstance(column.type, Enum)
    and column.type.create_constraint
    and column.type.name is not None
)
postgres_identifier_preparer = postgresql.dialect().identifier_preparer
enum_check_names = enum_check_logical_names | frozenset(
    postgres_identifier_preparer.truncate_and_render_constraint_name(
        conv(name), _alembic_quote=False
    )
    for name in enum_check_logical_names
)


def include_schema_object(
    _object: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Ignore reflected checks already represented by portable enum columns.

    Portable enum membership changes require an explicit migration.
    """
    explicit_search_objects = {
        "search_vector",
        "ix_request_search_documents_search_vector",
        "ix_request_search_documents_trigram",
        "ix_request_search_documents_embedding_hnsw",
    }
    if reflected and compare_to is None and name in explicit_search_objects:
        return False
    return not (
        type_ == "check_constraint"
        and reflected
        and compare_to is None
        and name in enum_check_names
    )


def compare_server_default(
    _context: Any,
    _inspected_column: Any,
    metadata_column: Any,
    inspected_default: str | None,
    _metadata_default: Any,
    rendered_metadata_default: str | None,
) -> bool | None:
    """Compare JSON defaults without invoking PostgreSQL's absent JSON equality."""
    if not isinstance(metadata_column.type, JSON):
        return None
    return _normalise_json_default(inspected_default) != _normalise_json_default(
        rendered_metadata_default
    )


def _normalise_json_default(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = value.strip().lower()
    for cast in ("::jsonb", "::json"):
        normalised = normalised.removesuffix(cast)
    while normalised.startswith("(") and normalised.endswith(")"):
        normalised = normalised[1:-1].strip()
    return normalised


def database_url() -> str:
    """Return the explicitly configured product database URL."""
    value = os.getenv("DATABASE_URL")
    if not value:
        message = "DATABASE_URL must be set before running Alembic"
        raise RuntimeError(message)
    return value


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=compare_server_default,
        compare_type=True,
        include_object=include_schema_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    """Run migrations against an established synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=compare_server_default,
        compare_type=True,
        include_object=include_schema_object,
        render_as_batch=connection.dialect.name == "sqlite",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and adapt its connection for Alembic."""
    escaped_url = database_url().replace("%", "%%")
    config.set_main_option("sqlalchemy.url", escaped_url)
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
