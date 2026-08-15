"""Bounded-query checks for request configuration-policy projection."""

from uuid import uuid4

import pytest
from sqlalchemy import event

from mist_service.config import Environment, Settings
from mist_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from mist_service.repositories.configuration_policies import (
    load_request_configuration_policies,
)


@pytest.mark.asyncio
async def test_request_policy_loading_chunks_broad_visibility_sets() -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
    )
    engine = create_database_engine(settings)
    await create_schema(engine)
    sessions = create_session_factory(engine)
    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if "request_configuration_pins" in statement:
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        async with sessions() as session:
            policies = await load_request_configuration_policies(
                session,
                {uuid4() for _ in range(501)},
            )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)
        await engine.dispose()

    assert policies == {}
    assert len(statements) == 2
