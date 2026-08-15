"""Database-backed planning concurrency invariants."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mist_service.repositories.board import SqlAlchemyBoardRepository
from mist_service.repositories.board_planning_commands import _constraint_name

MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0034_planning_concurrency_invariants.py"
)
CONSTRAINT = "capacity_reservations_active_no_overlap"


def test_constraint_name_finds_wrapped_and_diagnostic_names() -> None:
    direct = RuntimeError("direct")
    direct.constraint_name = CONSTRAINT  # type: ignore[attr-defined]
    wrapper = RuntimeError("wrapper")
    wrapper.__cause__ = direct
    assert _constraint_name(wrapper) == CONSTRAINT

    diagnostic = type("Diagnostic", (), {"constraint_name": CONSTRAINT})()
    diagnosed = RuntimeError("diagnosed")
    diagnosed.diag = diagnostic  # type: ignore[attr-defined]
    assert _constraint_name(diagnosed) == CONSTRAINT
    assert _constraint_name(RuntimeError("unknown")) is None


def test_migration_defines_partial_gist_exclusion_constraint() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS btree_gist" in source
    assert f"ADD CONSTRAINT {CONSTRAINT}" in source
    assert "EXCLUDE USING gist" in source
    assert "user_id WITH =" in source
    assert "tstzrange(starts_at, ends_at, '[)') WITH &&" in source
    assert "WHERE (status = 'ACTIVE')" in source


@pytest.mark.asyncio
async def test_postgresql_rejects_one_of_two_concurrent_active_reservations() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")

    engine = create_async_engine(database_url)
    schema = f"reservation_race_{uuid4().hex}"
    table = f"reservation_race_{uuid4().hex}"
    user_id = uuid4()
    starts_at = datetime(2026, 8, 13, 13, tzinfo=UTC)
    ends_at = starts_at + timedelta(hours=1)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
            await connection.execute(
                text(
                    f"""
                    CREATE TABLE {schema}.{table} (
                        id uuid PRIMARY KEY,
                        user_id uuid NOT NULL,
                        starts_at timestamptz NOT NULL,
                        ends_at timestamptz NOT NULL,
                        status text NOT NULL
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    f"""
                    ALTER TABLE {schema}.{table}
                    ADD CONSTRAINT {CONSTRAINT}
                    EXCLUDE USING gist (
                        user_id WITH =,
                        tstzrange(starts_at, ends_at, '[)') WITH &&
                    ) WHERE (status = 'ACTIVE')
                    """
                )
            )

        ready = asyncio.Event()
        release = asyncio.Event()
        insert_statement = text(
            f"INSERT INTO {schema}.{table} "  # noqa: S608
            "(id, user_id, starts_at, ends_at, status) "
            "VALUES (:id, :user_id, :starts_at, :ends_at, 'ACTIVE')"
        )

        async def insert(reservation_id: object, pause: bool) -> str:
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        insert_statement,
                        {
                            "id": reservation_id,
                            "user_id": user_id,
                            "starts_at": starts_at,
                            "ends_at": ends_at,
                        },
                    )
                    if pause:
                        ready.set()
                        await release.wait()
                return "committed"
            except DBAPIError as error:
                assert _constraint_name(error) == CONSTRAINT
                return "conflict"

        first = asyncio.create_task(insert(uuid4(), True))
        await asyncio.wait_for(ready.wait(), timeout=5)
        second = asyncio.create_task(insert(uuid4(), False))
        await asyncio.sleep(0.1)
        release.set()
        results = await asyncio.gather(first, second)
        assert sorted(results) == ["committed", "conflict"]
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_named_conflict_maps_to_deterministic_board_error() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine = create_async_engine(database_url)
    schema = f"reservation_mapping_{uuid4().hex}"
    table = f"reservation_mapping_{uuid4().hex}"
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
            await connection.execute(
                text(
                    f"CREATE TABLE {schema}.{table} ("
                    "id uuid PRIMARY KEY, user_id uuid NOT NULL, "
                    "starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL, "
                    "status text NOT NULL)"
                )
            )
            await connection.execute(
                text(
                    f"ALTER TABLE {schema}.{table} ADD CONSTRAINT {CONSTRAINT} "
                    "EXCLUDE USING gist (user_id WITH =, "
                    "tstzrange(starts_at, ends_at, '[)') WITH &&) "
                    "WHERE (status = 'ACTIVE')"
                )
            )
        user_id, starts_at = uuid4(), datetime(2026, 8, 13, 15, tzinfo=UTC)
        async with engine.connect() as connection:
            transaction = await connection.begin()
            statement = text(
                f"INSERT INTO {schema}.{table} VALUES "  # noqa: S608
                "(:id,:user,:starts,:ends,'ACTIVE')"
            )
            values = {
                "user": user_id,
                "starts": starts_at,
                "ends": starts_at + timedelta(hours=1),
            }
            await connection.execute(statement, {**values, "id": uuid4()})
            with pytest.raises(DBAPIError) as caught:
                await connection.execute(statement, {**values, "id": uuid4()})
            await transaction.rollback()
        assert _constraint_name(caught.value) == CONSTRAINT
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_team_lock_serialises_concurrent_wip_admission() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine, sessions, schema, team_id = await _planning_lock_database(database_url)
    first_id, second_id = uuid4(), uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(f"INSERT INTO {schema}.work_packages VALUES (:id,:team,'BACKLOG')"),  # noqa: S608
            [{"id": first_id, "team": team_id}, {"id": second_id, "team": team_id}],
        )
    ready, release = asyncio.Event(), asyncio.Event()

    async def admit(package_id: object, pause: bool) -> str:
        async with sessions() as session, session.begin():
            await session.execute(text(f"SET LOCAL search_path TO {schema}"))
            await SqlAlchemyBoardRepository(session).lock_planning_aggregate(team_id)
            count = await session.scalar(
                text("SELECT count(*) FROM work_packages WHERE status = 'READY'")
            )
            if count and count >= 1:
                return "wip-conflict"
            await session.execute(
                text("UPDATE work_packages SET status='READY' WHERE id=:id"),
                {"id": package_id},
            )
            if pause:
                ready.set()
                await release.wait()
        return "admitted"

    try:
        first = asyncio.create_task(admit(first_id, True))
        await asyncio.wait_for(ready.wait(), timeout=5)
        second = asyncio.create_task(admit(second_id, False))
        await asyncio.sleep(0.1)
        assert not second.done()
        release.set()
        assert sorted(await asyncio.gather(first, second)) == [
            "admitted",
            "wip-conflict",
        ]
    finally:
        await _drop_schema(engine, schema)


@pytest.mark.asyncio
async def test_postgresql_team_lock_serialises_dependency_cycle_checks() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine, sessions, schema, team_id = await _planning_lock_database(database_url)
    first_id, second_id = uuid4(), uuid4()
    ready, release = asyncio.Event(), asyncio.Event()

    async def add_edge(source: object, target: object, pause: bool) -> str:
        async with sessions() as session, session.begin():
            await session.execute(text(f"SET LOCAL search_path TO {schema}"))
            await SqlAlchemyBoardRepository(session).lock_planning_aggregate(team_id)
            reverse = await session.scalar(
                text(
                    "SELECT 1 FROM work_package_dependencies "
                    "WHERE package_id=:target AND depends_on_id=:source"
                ),
                {"source": source, "target": target},
            )
            if reverse:
                return "cycle-conflict"
            await session.execute(
                text("INSERT INTO work_package_dependencies VALUES (:source,:target)"),
                {"source": source, "target": target},
            )
            if pause:
                ready.set()
                await release.wait()
        return "added"

    try:
        first = asyncio.create_task(add_edge(first_id, second_id, True))
        await asyncio.wait_for(ready.wait(), timeout=5)
        second = asyncio.create_task(add_edge(second_id, first_id, False))
        await asyncio.sleep(0.1)
        assert not second.done()
        release.set()
        assert sorted(await asyncio.gather(first, second)) == [
            "added",
            "cycle-conflict",
        ]
    finally:
        await _drop_schema(engine, schema)


async def _planning_lock_database(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], str, UUID]:
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"planning_race_{uuid4().hex}"
    team_id = uuid4()
    async with engine.begin() as connection:
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
        statements = (
            f"CREATE TABLE {schema}.organisation_units (id uuid PRIMARY KEY)",
            f"CREATE TABLE {schema}.work_packages ("
            "id uuid PRIMARY KEY, team_id uuid NOT NULL, status text NOT NULL)",
            f"CREATE TABLE {schema}.work_package_dependencies ("
            "package_id uuid NOT NULL, depends_on_id uuid NOT NULL, "
            "PRIMARY KEY (package_id, depends_on_id))",
        )
        for statement in statements:
            await connection.execute(text(statement))
        await connection.execute(
            text(
                f"INSERT INTO {schema}.organisation_units "  # noqa: S608
                "VALUES (:team_id)"
            ),
            {"team_id": team_id},
        )
    return engine, sessions, schema, team_id


async def _drop_schema(engine: AsyncEngine, schema: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    await engine.dispose()
