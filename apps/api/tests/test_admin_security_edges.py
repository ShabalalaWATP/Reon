"""Security and integrity edge coverage for platform administration."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from conftest import ApiHarness
from istari_service.admin_audit import (
    append_admin_event,
    initialise_admin_audit_anchor,
    verify_admin_audit_integrity,
)
from istari_service.admin_models import (
    ADMIN_AUDIT_ANCHOR_ID,
    AdminAuditAnchor,
    AdminAuditEvent,
    AdminIdentitySequence,
)
from istari_service.admin_sequence import initialise_admin_identity_sequence
from istari_service.audit import canonical_anchor_mac
from istari_service.auth_service import PasswordHasher
from istari_service.domain import Actor
from istari_service.errors import InvalidAdministrationChange
from istari_service.models import User, UserRole
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.repositories.event_store import audit_key_for_session
from istari_service.schemas.admin import AdminStatusPatch
from istari_service.services.admin_service import AdminService


async def _login_admin(harness: ApiHarness) -> None:
    await harness.login("admin1")
    await harness.elevate()


async def _create_audited_user(harness: ApiHarness) -> None:
    await _login_admin(harness)
    response = await harness.client.post(
        "/api/v1/admin/users",
        json={
            "displayName": "Audit Edge Account",
            "role": "REQUESTER",
            "scope": "Requesting Area F",
            "organisationUnitIds": [],
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text


async def test_audit_empty_missing_anchor_and_lazy_recreation(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session, session.begin():
        assert await verify_admin_audit_integrity(session)
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None
        await session.delete(anchor)
    async with harness.sessions() as session:
        assert await verify_admin_audit_integrity(session)

    await _create_audited_user(harness)
    async with harness.sessions() as session:
        assert await verify_admin_audit_integrity(session)
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None and anchor.event_count == 1


async def test_audit_detects_anchor_count_link_event_and_head_tampering(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _create_audited_user(harness)

    async with harness.sessions() as session:
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        event = await session.scalar(select(AdminAuditEvent))
        assert anchor is not None and event is not None
        original_mac = anchor.anchor_mac
        anchor.anchor_mac = "0" * 64
        assert not await verify_admin_audit_integrity(session)
        anchor.anchor_mac = original_mac
        await session.rollback()

    async with harness.sessions() as session:
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None
        anchor.event_count += 1
        anchor.anchor_mac = canonical_anchor_mac(
            request_id=anchor.id,
            event_count=anchor.event_count,
            head_hash=anchor.head_hash or "",
            audit_key=audit_key_for_session(session),
        )
        assert not await verify_admin_audit_integrity(session)
        await session.rollback()

    async with harness.sessions() as session:
        event = await session.scalar(select(AdminAuditEvent))
        assert event is not None
        event.previous_hash = "1" * 64
        assert not await verify_admin_audit_integrity(session)
        await session.rollback()

    async with harness.sessions() as session:
        event = await session.scalar(select(AdminAuditEvent))
        assert event is not None
        event.event_hash = "2" * 64
        assert not await verify_admin_audit_integrity(session)
        await session.rollback()

    async with harness.sessions() as session:
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None
        key = audit_key_for_session(session)
        anchor.head_hash = "3" * 64
        anchor.anchor_mac = canonical_anchor_mac(
            request_id=anchor.id,
            event_count=anchor.event_count,
            head_hash=anchor.head_hash,
            audit_key=key,
        )
        assert not await verify_admin_audit_integrity(session)


async def test_audit_rejects_incomplete_nonempty_anchor_and_bad_key(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _create_audited_user(harness)
    async with harness.sessions() as session:
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None
        anchor.head_hash = None
        with session.no_autoflush:
            assert not await verify_admin_audit_integrity(session)
        await session.rollback()

    async with harness.sessions() as session:
        anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert anchor is not None
        await session.execute(delete(AdminAuditEvent))
        anchor.event_count = 0
        anchor.head_hash = None
        anchor.anchor_mac = None
        await session.flush()
        with pytest.raises(RuntimeError, match="audit HMAC key"):
            session.info.clear()
            await append_admin_event(
                session,
                actor_id=await harness.user_id("admin1"),
                action="TEST",
                target_type="USER",
                target_id=uuid4(),
                changed_fields=[],
                summary="Synthetic integrity test.",
            )


async def test_sequence_reconciles_upward_and_is_monotonic(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session, session.begin():
        sequence = await session.get(AdminIdentitySequence, 1)
        assert sequence is not None
        sequence.next_value = 1
        await initialise_admin_identity_sequence(session)
        assert sequence.next_value == 100
        repository = SqlAlchemyAdminRepository(session)
        assert await repository.next_username() == "admin100"
        assert await repository.next_username() == "admin101"
        await initialise_admin_identity_sequence(session)
        assert sequence.next_value == 102


async def test_initialisers_create_absent_rows(api_harness: ApiHarness) -> None:
    harness = api_harness
    async with harness.sessions() as session, session.begin():
        await session.execute(delete(AdminAuditEvent))
        await session.execute(delete(AdminAuditAnchor))
        await session.execute(delete(AdminIdentitySequence))
        await initialise_admin_audit_anchor(session)
        await initialise_admin_identity_sequence(session)
        assert await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
        assert await session.get(AdminIdentitySequence, 1)


async def test_last_admin_guard_with_distinct_actor(api_harness: ApiHarness) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        target = await session.scalar(select(User).where(User.username == "admin1"))
        approver = await session.scalar(select(User).where(User.username == "admin73"))
        assert target is not None and approver is not None
        approver.is_active = False
        await session.flush()
        repository = SqlAlchemyAdminRepository(session)
        service = AdminService(
            repository,
            harness.settings,
            PasswordHasher(time_cost=1, memory_cost=8_192, parallelism=1),
        )
        actor = Actor(
            id=uuid4(),
            username="external-admin-actor",
            display_name="External Administrator",
            role=UserRole.PLATFORM_ADMIN,
            scope="Platform support",
        )
        with pytest.raises(InvalidAdministrationChange, match="must remain"):
            await service.set_user_status(
                actor,
                target.id,
                AdminStatusPatch(is_active=False, expected_version=target.version),
            )


async def test_command_rename_does_not_rewrite_shared_user_scope_or_session(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.settings.configuration_admin_enabled = False
    await harness.login("admin5")
    shared_cookie = harness.client.cookies.get(harness.settings.session_cookie_name)
    assert shared_cookie is not None
    await _login_admin(harness)
    organisation = await harness.client.get("/api/v1/organisation/units")
    sygoc = next(
        item for item in organisation.json()["items"] if item["code"] == "SYGOC"
    )
    renamed = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{sygoc['id']}",
        json={"name": "SYGOC Services", "expectedVersion": sygoc["version"]},
        headers=harness.mutation_headers(),
    )
    assert renamed.status_code == 200
    harness.client.cookies.clear()
    harness.client.cookies.set(harness.settings.session_cookie_name, shared_cookie)
    current = await harness.client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["user"]["scope"] == "Shared request coordination"
