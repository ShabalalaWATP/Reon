"""Append and verify the isolated administrative audit chain."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.admin_models import (
    ADMIN_AUDIT_ANCHOR_ID,
    AdminAuditAnchor,
    AdminAuditEvent,
)
from istari_service.audit import canonical_anchor_mac
from istari_service.audit_types import AdminAuditEvidence
from istari_service.repositories.event_store import (
    active_audit_key_for_session,
    audit_key_for_session,
)


async def initialise_admin_audit_anchor(session: AsyncSession) -> None:
    anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
    if anchor is None:
        session.add(AdminAuditAnchor(id=ADMIN_AUDIT_ANCHOR_ID))
        await session.flush()


def admin_event_hash(
    *,
    sequence: int,
    actor_id: UUID,
    action: str,
    target_type: str,
    target_id: str,
    changed_fields: list[str],
    summary: str,
    created_at: datetime,
    previous_hash: str | None,
    audit_key: bytes,
) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    payload = AdminAuditEvidence(
        sequence=sequence,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        changed_fields=changed_fields,
        summary=summary,
        created_at=created_at.astimezone(UTC),
        previous_hash=previous_hash,
    ).canonical_payload()
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hmac.new(audit_key, canonical, hashlib.sha256).hexdigest()


async def append_admin_event(
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID,
    changed_fields: list[str],
    summary: str,
) -> AdminAuditEvent:
    anchor = await session.get(
        AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID, with_for_update=True
    )
    if anchor is None:
        anchor = AdminAuditAnchor(id=ADMIN_AUDIT_ANCHOR_ID)
        session.add(anchor)
        await session.flush()
    key_id, key = active_audit_key_for_session(session)
    created_at = datetime.now(UTC)
    sequence = anchor.event_count + 1
    event_hash = admin_event_hash(
        sequence=sequence,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        changed_fields=changed_fields,
        summary=summary,
        created_at=created_at,
        previous_hash=anchor.head_hash,
        audit_key=key,
    )
    event = AdminAuditEvent(
        anchor_id=anchor.id,
        actor_user_id=actor_id,
        sequence=sequence,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        changed_fields=sorted(changed_fields),
        summary=summary,
        previous_hash=anchor.head_hash,
        event_hash=event_hash,
        audit_key_id=key_id,
        created_at=created_at,
    )
    session.add(event)
    anchor.event_count = sequence
    anchor.head_hash = event_hash
    anchor.anchor_mac = canonical_anchor_mac(
        request_id=anchor.id,
        event_count=sequence,
        head_hash=event_hash,
        audit_key=key,
    )
    anchor.anchor_key_id = key_id
    await session.flush()
    return event


async def verify_admin_audit_integrity(session: AsyncSession) -> bool:
    anchor = await session.get(AdminAuditAnchor, ADMIN_AUDIT_ANCHOR_ID)
    if anchor is None:
        return True
    if anchor.event_count == 0:
        return anchor.head_hash is None and anchor.anchor_mac is None
    if anchor.head_hash is None or anchor.anchor_mac is None:
        return False
    expected_mac = canonical_anchor_mac(
        request_id=anchor.id,
        event_count=anchor.event_count,
        head_hash=anchor.head_hash,
        audit_key=audit_key_for_session(
            session, getattr(anchor, "anchor_key_id", None) or "legacy"
        ),
    )
    if not hmac.compare_digest(anchor.anchor_mac, expected_mac):
        return False
    events = (
        await session.scalars(
            select(AdminAuditEvent)
            .where(AdminAuditEvent.anchor_id == anchor.id)
            .order_by(AdminAuditEvent.sequence)
        )
    ).all()
    if len(events) != anchor.event_count:
        return False
    previous: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence or event.previous_hash != previous:
            return False
        calculated = admin_event_hash(
            sequence=event.sequence,
            actor_id=event.actor_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            changed_fields=event.changed_fields,
            summary=event.summary,
            created_at=event.created_at,
            previous_hash=previous,
            audit_key=audit_key_for_session(
                session, getattr(event, "audit_key_id", "legacy")
            ),
        )
        if not hmac.compare_digest(event.event_hash, calculated):
            return False
        previous = calculated
    return hmac.compare_digest(anchor.head_hash, previous or "")
