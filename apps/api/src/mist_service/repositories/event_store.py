"""Append-only, hash-linked request event persistence."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.analytics_projection import project_request_analytics
from mist_service.audit import (
    AUDIT_ACTIVE_KEY_ID_INFO,
    AUDIT_KEY_INFO,
    AUDIT_KEYRING_INFO,
    canonical_anchor_mac,
    canonical_event_hash,
)
from mist_service.audit_types import AuditEventEvidence, validate_audit_details
from mist_service.models import (
    RequestStatus,
    ServiceRequest,
)
from mist_service.request_event_audience import RequestEventAudience
from mist_service.request_event_models import RequestEvent
from mist_service.request_event_projection import project_request_event


async def append_request_event(
    session: AsyncSession,
    *,
    request_id: UUID,
    actor_id: UUID | None,
    event_type: str,
    message: str,
    prior_status: RequestStatus | None,
    next_status: RequestStatus | None,
    audience: RequestEventAudience | None = None,
    details: Mapping[str, object] | None = None,
) -> RequestEvent:
    """Append one event linked to the latest hash for this request."""

    request = await session.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise LookupError("request audit anchor is unavailable")
    previous_hash = request.audit_head_hash
    key_id, audit_key = active_audit_key_for_session(session)
    created_at = datetime.now(UTC)
    safe_details = validate_audit_details(details)
    effective_audience = audience or RequestEventAudience.STAFF_ONLY
    event_hash = canonical_event_hash(
        request_id=request_id,
        event_type=event_type,
        message=message,
        actor_id=actor_id,
        created_at=created_at,
        previous_hash=previous_hash,
        audit_key=audit_key,
        prior_status=prior_status,
        next_status=next_status,
        details=safe_details,
        audience=effective_audience.value,
        hash_version=2,
    )
    event = RequestEvent(
        request_id=request_id,
        actor_user_id=actor_id,
        type=event_type,
        message=message,
        audience=effective_audience,
        prior_status=prior_status,
        next_status=next_status,
        details=safe_details,
        previous_hash=previous_hash,
        event_hash=event_hash,
        audit_key_id=key_id,
        hash_version=2,
        created_at=created_at,
    )
    session.add(event)
    request.audit_event_count += 1
    request.audit_head_hash = event_hash
    request.audit_anchor_mac = canonical_anchor_mac(
        request_id=request.id,
        event_count=request.audit_event_count,
        head_hash=event_hash,
        audit_key=audit_key,
    )
    request.audit_anchor_key_id = key_id
    await session.flush()
    await project_request_analytics(session, request_id)
    await project_request_event(session, event, request)
    return event


async def verify_request_event_integrity(
    session: AsyncSession,
    request_id: UUID,
) -> bool:
    """Compare the complete stored chain with its request-owned head and count."""

    request = await session.get(ServiceRequest, request_id)
    if request is None:
        return False
    if request.audit_event_count == 0:
        if request.audit_head_hash is not None or request.audit_anchor_mac is not None:
            return False
    elif (
        request.audit_head_hash is None
        or request.audit_anchor_mac is None
        or not hmac.compare_digest(
            request.audit_anchor_mac,
            canonical_anchor_mac(
                request_id=request.id,
                event_count=request.audit_event_count,
                head_hash=request.audit_head_hash,
                audit_key=audit_key_for_session(
                    session, getattr(request, "audit_anchor_key_id", None) or "legacy"
                ),
            ),
        )
    ):
        return False
    events = (
        await session.scalars(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
        )
    ).all()
    chain = [
        AuditEventEvidence(
            request_id=event.request_id,
            event_type=event.type,
            message=event.message,
            actor_id=event.actor_user_id,
            created_at=event.created_at,
            previous_hash=event.previous_hash,
            prior_status=event.prior_status,
            next_status=event.next_status,
            details=event.details,
            event_hash=event.event_hash,
            audience=event.audience.value,
            hash_version=event.hash_version,
        )
        for event in events
    ]
    if len(chain) != request.audit_event_count:
        return False
    previous_hash: str | None = None
    for event, evidence in zip(events, chain, strict=True):
        if evidence.previous_hash != previous_hash:
            return False
        calculated = canonical_event_hash(
            request_id=evidence.request_id,
            event_type=evidence.event_type,
            message=evidence.message,
            actor_id=evidence.actor_id,
            created_at=evidence.created_at,
            previous_hash=previous_hash,
            audit_key=audit_key_for_session(
                session, getattr(event, "audit_key_id", "legacy")
            ),
            prior_status=evidence.prior_status,
            next_status=evidence.next_status,
            details=evidence.validated_details(),
            audience=evidence.audience,
            hash_version=evidence.hash_version,
        )
        if not hmac.compare_digest(calculated, evidence.event_hash):
            return False
        previous_hash = calculated
    return request.audit_head_hash == previous_hash


def audit_key_for_session(session: AsyncSession, key_id: str | None = None) -> bytes:
    keyring = session.info.get(AUDIT_KEYRING_INFO)
    if isinstance(keyring, dict):
        selected = key_id or session.info.get(AUDIT_ACTIVE_KEY_ID_INFO)
        key = keyring.get(selected)
    else:
        key = session.info.get(AUDIT_KEY_INFO)
    if not isinstance(key, bytes) or len(key) < 32:
        raise RuntimeError("a valid audit HMAC key is required")
    return key


def active_audit_key_for_session(session: AsyncSession) -> tuple[str, bytes]:
    key_id = session.info.get(AUDIT_ACTIVE_KEY_ID_INFO, "legacy")
    if not isinstance(key_id, str):
        raise RuntimeError("a valid active audit HMAC key ID is required")
    return key_id, audit_key_for_session(session, key_id)
