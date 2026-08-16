"""Demo seeding refuses to guess when a current and a legacy identity both exist."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.demo_seed import seed_demo_users
from mist_service.models import User, UserRole
from test_demo_seed import (
    TEST_SHARED_PASSWORD,
    RecordingHasher,
    db_session,  # noqa: F401  (pytest resolves the fixture by name)
)


@pytest.mark.asyncio
async def test_seed_refuses_when_current_and_legacy_users_are_different_accounts(
    db_session: AsyncSession,  # noqa: F811  (the imported fixture, injected)
) -> None:
    """A legacy username is renamed onto the current one only when it is the
    same account. Two distinct accounts holding the current and legacy names
    cannot be merged safely, so seeding stops instead of picking one."""

    for username in ("admin1", "platform.admin@example.test"):
        db_session.add(
            User(
                username=username,
                email=f"{username.split('@')[0]}@conflict.example.test",
                display_name=f"Existing {username}",
                password_hash="existing-hash",
                role=UserRole.REQUESTER,
                scope="Existing scope",
                is_active=True,
            )
        )
    await db_session.flush()

    with pytest.raises(RuntimeError, match="both current and legacy demo users"):
        await seed_demo_users(
            db_session,
            RecordingHasher(),
            environment="test",
            enabled=True,
            shared_password=TEST_SHARED_PASSWORD,
        )
