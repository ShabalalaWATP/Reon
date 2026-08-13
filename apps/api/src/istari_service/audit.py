"""Tamper-evident hashing for append-only request events."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

from istari_service.audit_types import (
    AuditEventEvidence,
    validate_audit_details,
)

AUDIT_KEY_INFO = "audit_hmac_key"
AUDIT_KEYRING_INFO = "audit_hmac_keyring"
AUDIT_ACTIVE_KEY_ID_INFO = "audit_active_key_id"


def canonical_event_hash(
    *,
    request_id: UUID,
    event_type: str,
    message: str,
    actor_id: UUID | None,
    created_at: datetime,
    previous_hash: str | None,
    audit_key: bytes,
    prior_status: str | None = None,
    next_status: str | None = None,
    details: Mapping[str, object] | None = None,
    audience: str | None = None,
    hash_version: int = 1,
) -> str:
    """Hash stable event fields and the preceding event hash."""

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    payload: dict[str, object] = {
        "actorId": str(actor_id) if actor_id else None,
        "createdAt": created_at.astimezone(UTC).isoformat(timespec="microseconds"),
        "details": validate_audit_details(details),
        "eventType": event_type,
        "message": message,
        "nextStatus": next_status,
        "previousHash": previous_hash,
        "priorStatus": prior_status,
        "requestId": str(request_id),
    }
    if hash_version >= 2:
        if audience is None:
            raise ValueError("version 2 request event hashes require an audience")
        payload["audience"] = audience
        payload["hashVersion"] = hash_version
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hmac.new(audit_key, canonical, hashlib.sha256).hexdigest()


def canonical_anchor_mac(
    *,
    request_id: UUID,
    event_count: int,
    head_hash: str,
    audit_key: bytes,
) -> str:
    """Authenticate the mutable chain anchor held outside the event rows."""

    payload = json.dumps(
        {
            "eventCount": event_count,
            "headHash": head_hash,
            "requestId": str(request_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hmac.new(audit_key, payload, hashlib.sha256).hexdigest()


def verify_event_chain(
    events: Sequence[AuditEventEvidence],
    *,
    audit_key: bytes,
    expected_head_hash: str | None = None,
    expected_count: int | None = None,
) -> bool:
    """Validate ordered event dictionaries without mutating them."""

    if expected_count is not None and len(events) != expected_count:
        return False
    previous_hash: str | None = None
    for event in events:
        if event.previous_hash != previous_hash:
            return False
        calculated = canonical_event_hash(
            request_id=event.request_id,
            event_type=event.event_type,
            message=event.message,
            actor_id=event.actor_id,
            created_at=event.created_at,
            previous_hash=previous_hash,
            audit_key=audit_key,
            prior_status=event.prior_status,
            next_status=event.next_status,
            details=event.validated_details(),
            audience=event.audience,
            hash_version=event.hash_version,
        )
        if not hmac.compare_digest(calculated, event.event_hash):
            return False
        previous_hash = calculated
    return expected_head_hash is None or previous_hash == expected_head_hash
