"""PostgreSQL atomic password-assistance budget admission."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from istari_service.platform_security_composition import platform_security_service
from istari_service.services.platform_security_service import (
    SOURCE_ATTEMPT_LIMIT,
)


async def test_password_assistance_budget_is_atomic_under_concurrent_calls() -> None:
    database_url = os.getenv("ISTARI_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("ISTARI_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"password_assistance_lock_{uuid4().hex}"
    source_key = f"synthetic-source-{uuid4().hex}"
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text(f"SET LOCAL search_path TO {schema}"))
            await connection.execute(
                text(
                    "CREATE TABLE platform_classification_settings ("
                    "id uuid PRIMARY KEY, classification text NOT NULL, "
                    "version integer NOT NULL, updated_by_user_id uuid, "
                    "created_at timestamptz NOT NULL DEFAULT now(), "
                    "updated_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            await connection.execute(
                text(
                    "CREATE TABLE password_assistance_attempts ("
                    "id uuid PRIMARY KEY, source_key varchar(72) NOT NULL, "
                    "matched_user_id uuid, email_hash varchar(64), "
                    "email_key_id varchar(64), "
                    "processing_status varchar(16) NOT NULL DEFAULT 'PENDING', "
                    "processing_attempts integer NOT NULL DEFAULT 0, "
                    "next_attempt_at timestamptz, processed_at timestamptz, "
                    "created_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO platform_classification_settings "
                    "(id,classification,version) "
                    "VALUES ('00000000-0000-0000-0000-000000000002',"
                    "'OFFICIAL',1)"
                )
            )

        start = asyncio.Event()

        async def request(index: int) -> object:
            await start.wait()
            async with sessions() as session, session.begin():
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))
                await session.execute(text("SET LOCAL lock_timeout = '5s'"))
                await session.execute(text("SET LOCAL statement_timeout = '8s'"))
                service = platform_security_service(
                    session,
                    pseudonym_key=b"synthetic-postgres-race-test-key",
                )
                return await service.request_password_assistance(
                    f"unknown-{index}@istari.example.test",
                    source_key=source_key,
                    now=now,
                )

        tasks = [asyncio.create_task(request(index)) for index in range(8)]
        start.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        accepted = [attempt_id for attempt_id in results if attempt_id is not None]
        assert len(accepted) == SOURCE_ATTEMPT_LIMIT
        assert len(set(accepted)) == SOURCE_ATTEMPT_LIMIT

        async with engine.connect() as connection:
            await connection.execute(text(f"SET search_path TO {schema}"))
            stored = await connection.scalar(
                text(
                    "SELECT count(*) FROM password_assistance_attempts "
                    "WHERE source_key=:source_key"
                ),
                {"source_key": source_key},
            )
        assert stored == SOURCE_ATTEMPT_LIMIT
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
