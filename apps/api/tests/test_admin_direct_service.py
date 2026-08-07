"""Direct administration use-case coverage across transactional continuations."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from conftest import ApiHarness
from istari_service.admin_audit import (
    admin_event_hash,
    append_admin_event,
    verify_admin_audit_integrity,
)
from istari_service.admin_models import AdminIdentitySequence
from istari_service.auth_service import PasswordHasher
from istari_service.domain import Actor
from istari_service.models import User, UserRole
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.schemas.admin import (
    AdminOrganisationRename,
    AdminStatusPatch,
    AdminUserCreate,
    AdminUserPatch,
)
from istari_service.services.admin_service import AdminService


async def test_direct_service_happy_paths_cover_transactional_continuations(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        stored_actor = await session.scalar(
            select(User).where(User.username == "admin1")
        )
        assert stored_actor is not None
        actor = Actor(
            id=stored_actor.id,
            username=stored_actor.username,
            display_name=stored_actor.display_name,
            role=stored_actor.role,
            scope=stored_actor.scope,
        )
        repository = SqlAlchemyAdminRepository(session)
        service = AdminService(
            repository,
            harness.settings,
            PasswordHasher(time_cost=1, memory_cost=8_192, parallelism=1),
        )
        created = await service.create_user(
            actor,
            AdminUserCreate(
                display_name="Direct Service Account",
                role=UserRole.REQUESTER,
                scope="Requesting Area H",
                organisation_unit_ids=[],
            ),
        )
        updated = await service.update_user(
            actor,
            created.id,
            AdminUserPatch(
                display_name="Direct Service Account Renamed",
                role=UserRole.REQUESTER,
                scope="Requesting Area H",
                organisation_unit_ids=[],
                expected_version=created.version,
            ),
        )
        deactivated = await service.set_user_status(
            actor,
            created.id,
            AdminStatusPatch(is_active=False, expected_version=updated.version),
        )
        reactivated = await service.set_user_status(
            actor,
            created.id,
            AdminStatusPatch(
                is_active=True,
                expected_version=deactivated.version,
            ),
        )
        assert reactivated.is_active

        cedar = await repository.load_units([await harness.unit_id("CEDAR_TEAM")])
        renamed = await service.rename_unit(
            actor,
            cedar[0].id,
            AdminOrganisationRename(
                name="Cedar Direct Service Team",
                expected_version=cedar[0].version,
            ),
        )
        assert renamed.name == "Cedar Direct Service Team"
        assert await repository.list_users(None)
        assert await repository.views([]) == []
        await repository.recalculate_teams(set())
        await session.rollback()


async def test_direct_valid_append_and_sequence_tampering(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        actor_id = await session.scalar(
            select(User.id).where(User.username == "admin1")
        )
        assert actor_id is not None
        event = await append_admin_event(
            session,
            actor_id=actor_id,
            action="DIRECT_TEST",
            target_type="USER",
            target_id=actor_id,
            changed_fields=["scope"],
            summary="Direct synthetic audit event.",
        )
        assert event.sequence == 1
        assert await verify_admin_audit_integrity(session)
        event.sequence = 2
        assert not await verify_admin_audit_integrity(session)
        await session.rollback()

    digest = admin_event_hash(
        sequence=1,
        actor_id=uuid4(),
        action="NAIVE_TIME_TEST",
        target_type="USER",
        target_id=str(uuid4()),
        changed_fields=[],
        summary="Naive timestamp normalisation test.",
        created_at=datetime(2026, 8, 6),  # noqa: DTZ001
        previous_hash=None,
        audit_key=b"a" * 32,
    )
    assert len(digest) == 64


async def test_missing_identity_sequence_fails_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        await session.execute(delete(AdminIdentitySequence))
        repository = SqlAlchemyAdminRepository(session)
        with pytest.raises(RuntimeError, match="identity sequence"):
            await repository.next_username()
        await session.rollback()
