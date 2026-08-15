"""PostgreSQL legal-hold operations through the maintenance role."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from mist_service.legal_holds import LEGAL_HOLD_AUTHORITY, LegalHoldService
from mist_service.postgres_permissions import permission_statements


@pytest.mark.asyncio
async def test_maintenance_role_can_apply_and_release_legal_hold() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL role tests")

    engine = create_async_engine(database_url)
    role = f"legal_hold_test_{uuid4().hex[:12]}"
    role_created = False
    try:
        async with engine.begin() as owner:
            target_id = uuid4()
            await owner.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS security_events ("
                    "id uuid PRIMARY KEY, event_type varchar(80) NOT NULL, "
                    "outcome varchar(20) NOT NULL, actor_user_id uuid, "
                    "subject_hash varchar(64), source_hash varchar(64), "
                    "reason_code varchar(80) NOT NULL, correlation_id varchar(80), "
                    "request_method varchar(10), route_template varchar(160), "
                    "deduplication_key varchar(64), "
                    "created_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            await owner.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS legal_holds ("
                    "id uuid PRIMARY KEY, "
                    "created_at timestamptz NOT NULL DEFAULT now(), "
                    "target_type varchar(40) NOT NULL, target_id varchar(64) NOT NULL, "
                    "reason_code varchar(80) NOT NULL, "
                    "authorised_by varchar(160) NOT NULL, "
                    "released_at timestamptz, released_by varchar(160))"
                )
            )
            await owner.execute(
                text(
                    "INSERT INTO security_events "
                    "(id,event_type,outcome,reason_code) "
                    "VALUES (:id,'LEGAL_HOLD_TEST','SUCCESS','SYNTHETIC_TEST')"
                ),
                {"id": target_id},
            )
            await owner.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
            role_created = True
            statements = permission_statements("unused_runtime", "unused_backup", role)
            for statement in statements:
                maintenance_grant = f'"{role}"' in statement and any(
                    grant in statement
                    for grant in (
                        "GRANT USAGE ON SCHEMA",
                        "GRANT SELECT ON ALL TABLES",
                        "legal_holds",
                    )
                )
                if maintenance_grant:
                    await owner.execute(text(statement))

        async with engine.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            session = AsyncSession(bind=connection, expire_on_commit=False)
            service = LegalHoldService(
                session,
                subject="synthetic-legal-hold-operator",
                authority=LEGAL_HOLD_AUTHORITY,
            )
            hold = await service.apply("SECURITY_EVENT", target_id, "LITIGATION")
            released = await service.release("SECURITY_EVENT", target_id)
            assert released.id == hold.id
            assert released.released_at is not None
            assert released.released_by == "synthetic-legal-hold-operator"
            await transaction.rollback()
            await session.close()
    finally:
        if role_created:
            async with engine.begin() as owner:
                await owner.execute(text(f'DROP OWNED BY "{role}"'))
                await owner.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
                await owner.execute(
                    text("DELETE FROM security_events WHERE id=:id"), {"id": target_id}
                )
        await engine.dispose()
