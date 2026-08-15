"""PostgreSQL final-boundary participant lock ordering."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mist_service.repositories.request_participants import (
    validate_request_participants,
)


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE users SET is_active=false WHERE id=:user_id",
        "UPDATE team_memberships SET effective_until=now() WHERE user_id=:user_id",
    ],
)
async def test_participant_validation_serialises_authority_revocation(
    mutation: str,
) -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("MIST_POSTGRES_TEST_URL is required for PostgreSQL race tests")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"participant_lock_{uuid4().hex}"
    request_id, user_id, team_id = uuid4(), uuid4(), uuid4()
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text(f"SET LOCAL search_path TO {schema}"))
            await connection.execute(
                text(
                    "CREATE TABLE users (id uuid PRIMARY KEY, is_active boolean, "
                    "role text)"
                )
            )
            await connection.execute(
                text(
                    "CREATE TABLE request_participants ("
                    "id uuid PRIMARY KEY, request_id uuid, user_id uuid, role text, "
                    "ended_at timestamptz)"
                )
            )
            await connection.execute(
                text(
                    "CREATE TABLE team_memberships ("
                    "id uuid PRIMARY KEY, user_id uuid, team_id uuid, "
                    "effective_from timestamptz, effective_until timestamptz)"
                )
            )
            await connection.execute(
                text("INSERT INTO users VALUES (:user_id,true,'DELIVERY_SPECIALIST')"),
                {"user_id": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO request_participants VALUES "
                    "(:participant_id,:request_id,:user_id,'LEAD',NULL)"
                ),
                {
                    "participant_id": uuid4(),
                    "request_id": request_id,
                    "user_id": user_id,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO team_memberships VALUES "
                    "(:membership_id,:user_id,:team_id,:started,NULL)"
                ),
                {
                    "membership_id": uuid4(),
                    "user_id": user_id,
                    "team_id": team_id,
                    "started": datetime(2026, 1, 1, tzinfo=UTC),
                },
            )

        validated = asyncio.Event()
        release = asyncio.Event()

        async def validate() -> None:
            async with sessions() as session, session.begin():
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))
                request = SimpleNamespace(
                    id=request_id,
                    assigned_delivery_team_id=team_id,
                    assigned_specialist_id=user_id,
                )
                assert await validate_request_participants(session, request) == {
                    user_id
                }
                validated.set()
                await release.wait()

        async def revoke() -> None:
            async with sessions() as session, session.begin():
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))
                await session.execute(text(mutation), {"user_id": user_id})

        validator = asyncio.create_task(validate())
        await asyncio.wait_for(validated.wait(), timeout=5)
        revocation = asyncio.create_task(revoke())
        await asyncio.sleep(0.1)
        assert not revocation.done()
        release.set()
        await asyncio.wait_for(asyncio.gather(validator, revocation), timeout=5)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
