"""Executable PostgreSQL assurance for revisions 0043 through 0047."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from postgres_migration_assertions import (
    assert_0043,
    assert_0044,
    assert_0045,
    assert_0046,
    assert_0047,
)
from postgres_migration_database import (
    create_assurance_databases,
    drop_assurance_databases,
)
from postgres_migration_downgrade_assertions import (
    assert_0044_downgrade,
    assert_0045_downgrade,
    assert_0046_downgrade,
    assert_0047_downgrade,
    assert_empty_forward_path,
    assert_reupgrade,
)

SOURCE_ROOT = Path(__file__).parents[1]
API_ROOT = SOURCE_ROOT if (SOURCE_ROOT / "alembic.ini").is_file() else Path.cwd()
REVISION_0043 = "0043_security_event_dedup"
REVISION_0044 = "0044_context_conversations"
REVISION_0045 = "0045_notification_contexts"
REVISION_0046 = "0046_product_package_policy"
REVISION_0047 = "0047_action_view_contexts"
Phase = Callable[[AsyncConnection], Awaitable[None]]


def run_postgres_migration_roundtrip(admin_database_url: str) -> None:
    """Execute the destructive assurance against a dedicated CI database."""

    database_url, empty_database_url, names = asyncio.run(
        create_assurance_databases(admin_database_url)
    )
    previous_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = database_url
        config = _alembic_config(database_url)
        _upgrade_and_assert(config, database_url, REVISION_0043, assert_0043)
        _upgrade_and_assert(config, database_url, REVISION_0044, assert_0044)
        _upgrade_and_assert(config, database_url, REVISION_0045, assert_0045)
        _upgrade_and_assert(config, database_url, REVISION_0046, assert_0046)
        _upgrade_and_assert(config, database_url, REVISION_0047, assert_0047)

        _downgrade_and_assert(
            config, database_url, REVISION_0046, assert_0047_downgrade
        )
        _downgrade_and_assert(
            config, database_url, REVISION_0045, assert_0046_downgrade
        )
        _downgrade_and_assert(
            config, database_url, REVISION_0044, assert_0045_downgrade
        )
        _downgrade_and_assert(
            config, database_url, REVISION_0043, assert_0044_downgrade
        )

        command.upgrade(config, "head")
        asyncio.run(_phase(database_url, assert_reupgrade))
        command.check(config)

        os.environ["DATABASE_URL"] = empty_database_url
        empty_config = _alembic_config(empty_database_url)
        command.upgrade(empty_config, "head")
        asyncio.run(_phase(empty_database_url, assert_empty_forward_path))
        command.check(empty_config)
    finally:
        try:
            asyncio.run(drop_assurance_databases(admin_database_url, names))
        finally:
            if previous_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_url


def _upgrade_and_assert(
    config: Config, database_url: str, revision: str, assertion: Phase
) -> None:
    command.upgrade(config, revision)
    asyncio.run(_phase(database_url, assertion))


def _downgrade_and_assert(
    config: Config, database_url: str, revision: str, assertion: Phase
) -> None:
    command.downgrade(config, revision)
    asyncio.run(_phase(database_url, assertion))


def _alembic_config(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def _phase(database_url: str, phase: Phase) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await phase(connection)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    arguments = parser.parse_args()
    if not arguments.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")
    run_postgres_migration_roundtrip(arguments.database_url)


if __name__ == "__main__":
    main()
