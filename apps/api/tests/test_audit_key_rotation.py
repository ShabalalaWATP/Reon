"""Audit-key rotation continuity regressions."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api_helpers import submit_request
from conftest import ApiHarness
from mist_service.admin_audit import append_admin_event, verify_admin_audit_integrity
from mist_service.audit import (
    AUDIT_ACTIVE_KEY_ID_INFO,
    AUDIT_KEY_INFO,
    AUDIT_KEYRING_INFO,
)
from mist_service.repositories.event_store import (
    active_audit_key_for_session,
    verify_request_event_integrity,
)


async def test_old_request_chain_remains_verifiable_after_active_key_rotation(
    api_harness: ApiHarness,
) -> None:
    request_id = UUID(await submit_request(api_harness))
    async with api_harness.sessions() as session:
        old_key = session.info[AUDIT_KEY_INFO]
        session.info[AUDIT_KEYRING_INFO] = {"legacy": old_key, "rotated": b"r" * 32}
        session.info[AUDIT_ACTIVE_KEY_ID_INFO] = "rotated"
        session.info[AUDIT_KEY_INFO] = b"r" * 32
        assert await verify_request_event_integrity(session, request_id)


async def test_old_admin_chain_remains_verifiable_after_active_key_rotation(
    api_harness: ApiHarness,
) -> None:
    actor_id = await api_harness.user_id("admin2")
    async with api_harness.sessions() as session, session.begin():
        await append_admin_event(
            session,
            actor_id=actor_id,
            action="rotation_test",
            target_type="configuration",
            target_id=actor_id,
            changed_fields=["safeField"],
            summary="Synthetic rotation continuity evidence.",
        )
    async with api_harness.sessions() as session:
        old_key = session.info[AUDIT_KEY_INFO]
        session.info[AUDIT_KEYRING_INFO] = {"legacy": old_key, "rotated": b"r" * 32}
        session.info[AUDIT_ACTIVE_KEY_ID_INFO] = "rotated"
        assert await verify_admin_audit_integrity(session)


def test_active_audit_key_rejects_non_string_identifier() -> None:
    class InvalidSession:
        def __init__(self) -> None:
            self.info = {
                AUDIT_ACTIVE_KEY_ID_INFO: 42,
                AUDIT_KEYRING_INFO: {"legacy": b"a" * 32},
            }

    with pytest.raises(RuntimeError, match="active audit HMAC key ID"):
        active_audit_key_for_session(cast(AsyncSession, InvalidSession()))
